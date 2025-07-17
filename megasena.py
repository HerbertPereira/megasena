import pandas as pd
import requests
from bs4 import BeautifulSoup
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import collections
import random
import os

# --- Função de Web Scraping Melhorada ---
@st.cache_data(ttl=3600) # Armazena em cache os dados por 1 hora para evitar scraping excessivo
def fetch_megasena_data():
    """
    Busca os resultados da Mega Sena do site oficial (https://www.megasena.com/resultados).
    Robustez melhorada ao procurar cabeçalhos específicos nas tabelas.
    """
    url = "https://www.megasena.com/resultados"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Levanta um HTTPError para respostas de erro (4xx ou 5xx)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        target_table = None
        # Tenta encontrar a tabela de resultados anteriores pelo título
        h2_previous_results = soup.find('h2', string='Resultados anteriores')
        if h2_previous_results:
            target_table = h2_previous_results.find_next_sibling('table', class_='_results _archive -center main-results')
        
        # Se não encontrar pela primeira forma, tenta encontrar qualquer tabela com a classe
        if not target_table:
            tables = soup.find_all('table', class_='_results _archive -center main-results')
            if len(tables) > 1: # Pega a segunda se houver, que geralmente é a de resultados anteriores
                target_table = tables[1]
            elif len(tables) == 1: # Se só houver uma, pega essa
                target_table = tables[0]
            
        if not target_table:
            st.error("Não foi possível encontrar a tabela de resultados da Mega Sena na página. O layout do site pode ter mudado.")
            return None

        data = []
        rows = target_table.find_all('tr')

        if len(rows) < 2:
            st.warning("Tabela encontrada, mas não contém linhas de dados suficientes para processamento.")
            return None

        for row in rows:
            # Ignora linhas de cabeçalho e banners da tabela
            if 'tbhead' in row.get('class', []) or 'table-banner' in row.get('class', []):
                continue

            cols = row.find_all('td')
            if len(cols) >= 4: # Garante que a linha tem colunas suficientes
                concurso_data_div = cols[0]
                concurso_tag = concurso_data_div.find('div', class_='draw-number')
                concurso_num = concurso_tag.find('a').text.replace('Concurso ', '').strip() if concurso_tag else None
                
                data_sorteio_str = concurso_data_div.find('div', class_='date').text.strip()
                
                balls_ul = cols[1].find('ul', class_='balls -lg')
                if balls_ul:
                    dezenas = [int(li.text.strip()) for li in balls_ul.find_all('li', class_='ball')]
                else:
                    st.warning(f"Não foi possível encontrar as dezenas para o concurso {concurso_num}. Ignorando linha.")
                    continue
                
                if concurso_num and len(dezenas) == 6:
                    data.append([concurso_num, data_sorteio_str] + dezenas)
                elif concurso_num:
                    st.warning(f"Concurso {concurso_num} tem {len(dezenas)} dezenas ({dezenas}), esperado 6. Ignorando linha.")
                    continue
            
        if not data:
            st.error("Nenhum dado válido de resultado da Mega Sena pôde ser extraído.")
            return None

        df = pd.DataFrame(data, columns=['Concurso', 'Data', 'Dezena1', 'Dezena2',
                                         'Dezena3', 'Dezena4', 'Dezena5', 'Dezena6'])
        
        # Converte 'Data' para datetime, tratando erros
        df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=['Data'], inplace=True) # Remove linhas com data inválida
        
        # Converte 'Concurso' para numérico, tratando erros
        df['Concurso'] = pd.to_numeric(df['Concurso'], errors='coerce')
        df.dropna(subset=['Concurso'], inplace=True) # Remove linhas com concurso inválido
        
        df = df.sort_values(by='Concurso', ascending=True).reset_index(drop=True)

        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao conectar ao site da Mega Sena. Verifique sua conexão com a internet ou tente novamente mais tarde: {e}")
        return None
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao buscar os dados: {e}")
        st.exception(e) # Mostra o stack trace completo para depuração
        return None

# --- Funções de Análise ---
@st.cache_data # Armazena em cache o resultado da análise
def analyze_numbers(data):
    numbers = []
    for i in range(1, 7):
        col_name = f'Dezena{i}'
        if col_name in data.columns:
            numbers.extend(data[col_name].dropna().tolist())
    
    numeric_numbers = [int(n) for n in numbers if isinstance(n, (int, float)) and 1 <= int(n) <= 60]

    if not numeric_numbers:
        st.warning("Nenhum número válido encontrado para análise de frequência.")
        return pd.Series(), [], [], [] 
    
    freq = pd.Series(numeric_numbers).value_counts().sort_values(ascending=False)

    most_common = freq.head(min(4, len(freq))).index.tolist()
    least_common = freq.tail(min(2, len(freq))).index.tolist()

    return freq, most_common, least_common, numeric_numbers

@st.cache_data # Armazena em cache o plot
def plot_frequencies(frequencies):
    if frequencies.empty:
        st.info("Nenhum dado de frequência para plotar.")
        return

    full_range_freq = pd.Series(0, index=range(1, 61))
    full_range_freq.update(frequencies)
    
    fig, ax = plt.subplots(figsize=(15, 7)) # Cria a figura e os eixos
    
    full_range_freq_sorted_by_num = full_range_freq.sort_index() 
    
    ax.bar(full_range_freq_sorted_by_num.index.astype(str), full_range_freq_sorted_by_num.values, color='skyblue')
    
    ax.set_title('Frequência dos Números da Mega Sena (1 a 60)', fontsize=16)
    ax.set_xlabel('Número', fontsize=14)
    ax.set_ylabel('Frequência de Sorteios', fontsize=14)
    
    # CORREÇÃO PARA set_xticks e set_xticklabels
    ax.set_xticks(full_range_freq_sorted_by_num.index) # Define as posições dos ticks
    ax.set_xticklabels(full_range_freq_sorted_by_num.index.astype(str), rotation=90, fontsize=10) # Define os rótulos e seus estilos

    ax.tick_params(axis='y', labelsize=10) 
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    st.pyplot(fig) # Passa a figura para st.pyplot
    plt.close(fig) # Fecha a figura para liberar memória

@st.cache_data
def analyze_outliers(frequencies):
    if frequencies.empty:
        return [], 0.0

    y = frequencies.values.astype(float)

    def moving_average(data, window_size):
        if window_size <= 0:
            return np.zeros_like(data)
        window = np.ones(int(window_size)) / float(window_size)
        return np.convolve(data, window, 'same')

    def explain_anomalies(y, window_size, sigma=1.0):
        if len(y) < window_size:
            return {'standard_deviation': 0.0, 'anomalies_dict': collections.OrderedDict()}

        avg = moving_average(y, window_size)
        residual = y - avg

        std = np.std(residual)

        anomalies = collections.OrderedDict()
        for i, (y_i, avg_i) in enumerate(zip(y, avg)):
            if (y_i > avg_i + (sigma * std)) or (y_i < avg_i - (sigma * std)):
                if i < len(frequencies.index):
                    anomalies[frequencies.index[i]] = y_i

        return {'standard_deviation': round(std, 2),
                'anomalies_dict': anomalies}

    window_size = min(10, len(frequencies) // 2 if len(frequencies) > 0 else 1)
    sigma_value = 1.5 

    events = explain_anomalies(y, window_size=window_size, sigma=sigma_value)
    outliers = list(events['anomalies_dict'].keys())

    return outliers, events['standard_deviation']

@st.cache_data
def calculate_probabilities(frequencies, total_possible_numbers=60):
    if frequencies.empty:
        return pd.Series()
    
    total_draws_count = frequencies.sum() 
    if total_draws_count == 0:
        return pd.Series()
        
    probabilities = (frequencies / total_draws_count) * 100 
    return probabilities.sort_values(ascending=False)

@st.cache_data
def analyze_delays(data, selected_numbers):
    if data.empty or not selected_numbers:
        return {}

    delays = {}
    last_concurso = data['Concurso'].max()
    
    for num in selected_numbers:
        num_occurrences = data[
            (data['Dezena1'] == num) | (data['Dezena2'] == num) |
            (data['Dezena3'] == num) | (data['Dezena4'] == num) |
            (data['Dezena5'] == num) | (data['Dezena6'] == num)
        ]
        
        if not num_occurrences.empty:
            last_appearance_concurso = num_occurrences['Concurso'].max()
            delay = last_concurso - last_appearance_concurso
            delays[num] = int(delay) 
        else:
            delays[num] = -1 # Indica que o número nunca apareceu nos dados carregados

    return delays

@st.cache_data
def analyze_drawing_patterns(data):
    if data.empty:
        return {}, {}

    data['SomaDezenas'] = data[['Dezena1', 'Dezena2', 'Dezena3', 'Dezena4', 'Dezena5', 'Dezena6']].sum(axis=1)
    avg_sum = data['SomaDezenas'].mean()
    
    even_counts = []
    odd_counts = []
    for _, row in data.iterrows():
        dezenas = [row[f'Dezena{i}'] for i in range(1, 7)]
        even_count = sum(1 for num in dezenas if num % 2 == 0)
        odd_count = 6 - even_count 
        even_counts.append(even_count)
        odd_counts.append(odd_count)
    
    even_odd_distribution = collections.Counter(zip(even_counts, odd_counts))
    even_odd_distribution = {f'{k[0]} Pares / {k[1]} Ímpares': v for k, v in even_odd_distribution.items()}
    
    return {'average_sum': round(avg_sum, 2)}, even_odd_distribution

# --- Sugestão de Números (Generalizada) ---
def suggest_numbers(most_common, least_common, num_to_suggest=6):
    """
    Sugere 'num_to_suggest' números com base em uma mistura dos mais e menos comuns,
    e alguns números aleatórios para preencher a lacuna. Garante a unicidade.
    """
    suggested_set = set()
    
    # Adiciona alguns dos números mais comuns
    for num in most_common:
        if len(suggested_set) < num_to_suggest:
            suggested_set.add(num)
        else:
            break
            
    # Adiciona alguns dos números menos comuns, garantindo que não sejam duplicados
    for num in least_common:
        if len(suggested_set) < num_to_suggest and num not in suggested_set:
            suggested_set.add(num)
        else:
            break
            
    # Preenche o restante com números aleatórios únicos de 1 a 60
    all_possible_numbers = set(range(1, 61))
    available_numbers = list(all_possible_numbers - suggested_set)
    random.shuffle(available_numbers)

    while len(suggested_set) < num_to_suggest and available_numbers:
        suggested_set.add(available_numbers.pop(0))
            
    final_suggestion = sorted(list(suggested_set))
    
    # Garante que a lista final tenha exatamente num_to_suggest elementos,
    # caso a combinação de mais/menos comuns já ultrapasse ou seja exatamente o limite.
    if len(final_suggestion) > num_to_suggest:
        final_suggestion = random.sample(final_suggestion, num_to_suggest)
        final_suggestion.sort() # Mantém ordenado
    elif len(final_suggestion) < num_to_suggest:
        # Isso só aconteceria se most_common e least_common fossem vazios e num_to_suggest > 0
        remaining_needed = num_to_suggest - len(final_suggestion)
        remaining_available = list(all_possible_numbers - suggested_set)
        random.shuffle(remaining_available)
        final_suggestion.extend(random.sample(remaining_available, min(remaining_needed, len(remaining_available))))
        final_suggestion.sort()

    return final_suggestion


# --- Tabela de Preços da Mega Sena ---
# Valores aproximados para referência, podem variar
MEGA_SENA_PRICES = {
    6: 5.00,
    7: 35.00,
    8: 140.00,
    9: 420.00,
    10: 1050.00,
    11: 2310.00,
    12: 4620.00,
    13: 8580.00,
    14: 15015.00,
    15: 25025.00,
    16: 40040.00,
    17: 61880.00,
    18: 92820.00,
    19: 135660.00,
    20: 193800.00
}

# --- Interface Streamlit Principal ---
def main():
    st.set_page_config(page_title="Analisador de Números da Mega Sena", layout="wide", initial_sidebar_state="collapsed")
    
    # Adiciona o logo no topo, com verificação de existência
    logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=250)
    else:
        st.warning("Arquivo 'logo.png' não encontrado. Verifique se está na mesma pasta do script para que o logo seja exibido.")

    st.title("🔢 Analisador de Números da Mega Sena")
    st.write("Esta ferramenta busca os resultados oficiais e realiza análises de frequência, probabilidades e padrões dos números sorteados.")

    st.markdown("---")

    # Inicializa variáveis no session_state se não existirem
    if 'data' not in st.session_state:
        st.session_state['data'] = None
    if 'freqs' not in st.session_state:
        st.session_state['freqs'] = None
    if 'most_common' not in st.session_state:
        st.session_state['most_common'] = None
    if 'least_common' not in st.session_state:
        st.session_state['least_common'] = None
    if 'num_dezenas_to_play' not in st.session_state:
        st.session_state['num_dezenas_to_play'] = 6
    if 'suggested_game' not in st.session_state:
        st.session_state['suggested_game'] = []

    # Botão para buscar dados, com lógica de cache e análise
    if st.button("📊 Buscar Últimos Resultados"):
        with st.spinner("Buscando resultados da Mega Sena..."):
            data = fetch_megasena_data()
        
        if data is None or data.empty:
            st.error("Não foi possível buscar os dados ou nenhum dado válido encontrado. Por favor, tente novamente mais tarde.")
            # Limpa o estado se a busca falhar
            st.session_state['data'] = None
            st.session_state['freqs'] = None
            st.session_state['most_common'] = None
            st.session_state['least_common'] = None
            st.session_state['suggested_game'] = [] 
            return # Sai da função main para evitar erros com dados vazios
        
        st.success(f"Dados dos {len(data)} últimos concursos carregados com sucesso!")
        st.session_state['data'] = data
        
        # Realiza a análise imediatamente após a busca
        freqs, most_common, least_common, all_numbers_flat = analyze_numbers(data)
        st.session_state['freqs'] = freqs
        st.session_state['most_common'] = most_common
        st.session_state['least_common'] = least_common
        
        # Gera uma sugestão inicial após os dados serem carregados
        st.session_state['suggested_game'] = suggest_numbers(
            st.session_state['most_common'], 
            st.session_state['least_common'], 
            st.session_state['num_dezenas_to_play']
        )
        st.rerun() # Força uma nova execução para exibir os dados atualizados e a sugestão

    # Exibe as seções de análise APENAS se os dados estiverem disponíveis
    if st.session_state['data'] is not None:
        data = st.session_state['data']
        freqs = st.session_state['freqs']
        most_common = st.session_state['most_common']
        least_common = st.session_state['least_common']

        if st.checkbox("Mostrar Tabela de Dados Brutos (últimos 10 concursos)", value=False):
            st.subheader("Dados Brutos dos Últimos Sorteios")
            st.dataframe(data.tail(10).style.format({'Concurso': '{:.0f}'}))

        st.markdown("---")

        if freqs.empty:
            st.warning("Não há dados de frequência disponíveis para análise.")
            # Não 'return' aqui, para permitir que as outras seções (incluindo a de sugestão) funcionem
        else:
            st.header("Análise de Frequência")
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("⭐ 4 Números Mais Sorteados (Quentes)")
                if most_common:
                    for i, num in enumerate(most_common, 1):
                        st.write(f"**{i}. Número {num}** (sorteado **{freqs.get(num, 0)}** vezes)")
                else:
                    st.info("Dados insuficientes para determinar os números mais sorteados.")

            with col2:
                st.subheader("❄️ 2 Números Menos Sorteados (Frios)")
                if least_common:
                    for i, num in enumerate(least_common, 1):
                        st.write(f"**{i}. Número {num}** (sorteado **{freqs.get(num, 0)}** vezes)")
                else:
                    st.info("Dados insuficientes para determinar os números menos sorteados.")

            st.markdown("---")

            st.subheader("📊 Distribuição de Frequência dos Números")
            plot_frequencies(freqs)

            st.markdown("---")

            st.header("Probabilidades e Atrasos")
            probabilities = calculate_probabilities(freqs)
            
            if not probabilities.empty:
                st.subheader("📈 Probabilidade Histórica de Cada Número")
                st.write("Probabilidade de cada número ser sorteado com base nos dados históricos (%):")
                prob_df = probabilities.reset_index()
                prob_df.columns = ['Número', 'Probabilidade (%)']
                st.dataframe(prob_df.style.format({'Probabilidade (%)': '{:.2f}%'}))
            else:
                st.info("Não foi possível calcular probabilidades.")
                
            st.subheader("⏳ Atrasos dos Números (Concursos sem Sorteio)")
            
            all_selected_for_delay = []
            if most_common:
                all_selected_for_delay.extend(most_common)
            if least_common:
                all_selected_for_delay.extend(least_common)

            if all_selected_for_delay:
                delays = analyze_delays(data, all_selected_for_delay)
                delay_df = pd.DataFrame(delays.items(), columns=['Número', 'Concursos sem aparecer'])
                delay_df['Concursos sem aparecer'] = delay_df['Concursos sem aparecer'].astype(int)
                delay_df = delay_df.sort_values(by='Concursos sem aparecer', ascending=False)
                st.dataframe(delay_df.style.format({'Concursos sem aparecer': '{:.0f}'}))
                st.write("- Um valor de **-1** indica que o número nunca apareceu nos dados históricos carregados.")
            else:
                st.info("Não há números selecionados para análise de atrasos.")

            st.markdown("---")

            st.header("Padrões e Estatísticas Gerais")
            
            general_stats, even_odd_dist = analyze_drawing_patterns(data)

            if general_stats:
                st.subheader("Sumário da Soma das Dezenas")
                st.write(f"A **soma média das dezenas** sorteadas em cada concurso é: **{general_stats['average_sum']:.2f}**")
            
            if even_odd_dist:
                st.subheader("Padrões de Pares e Ímpares")
                st.write("Frequência de combinações de números pares e ímpares:")
                even_odd_df = pd.DataFrame(even_odd_dist.items(), columns=['Combinação (Pares/Ímpares)', 'Frequência'])
                even_odd_df = even_odd_df.sort_values(by='Frequência', ascending=False).reset_index(drop=True)
                st.dataframe(even_odd_df)

            st.markdown("---")
            
            st.header("Detecção de Outliers")
            outliers, std = analyze_outliers(freqs)

            if outliers:
                st.write(f"Números com frequências significativamente mais altas ou mais baixas (usando desvio padrão σ={std:.2f}):")
                for num in outliers:
                    st.write(f"- **Número {num}** (Frequência: {freqs.get(num, 0)})")
            else:
                st.write("Nenhum outlier significativo detectado nas frequências dos números.")

        st.markdown("---")

        # --- SEÇÃO: Sugestão de Jogo e Preços ---
        st.header("🎲 Sugestão de Jogo e Preços")
        
        col_slider, col_button = st.columns([0.7, 0.3])

        with col_slider:
            # Slider para escolher a quantidade de dezenas
            current_num_dezenas = st.session_state['num_dezenas_to_play']
            new_num_dezenas = st.slider(
                'Quantas dezenas deseja jogar?', 
                min_value=6, 
                max_value=20, 
                value=current_num_dezenas,
                step=1,
                key='num_dezenas_slider' 
            )
            # Atualiza o estado se o slider for movido.
            # O Streamlit rerodará e o jogo sugerido será atualizado automaticamente
            # se houver dados e o `num_dezenas_to_play` tiver mudado.
            if new_num_dezenas != current_num_dezenas:
                st.session_state['num_dezenas_to_play'] = new_num_dezenas
                # Força a geração de um novo jogo com a nova quantidade de dezenas,
                # para que a sugestão mude imediatamente ao arrastar o slider.
                if st.session_state['most_common'] and st.session_state['least_common']:
                    st.session_state['suggested_game'] = suggest_numbers(
                        st.session_state['most_common'], 
                        st.session_state['least_common'], 
                        st.session_state['num_dezenas_to_play']
                    )
                st.rerun() # Força o Streamlit a rerodar para atualizar a sugestão imediatamente

        with col_button:
            st.write("") # Espaçamento para alinhar o botão
            st.write("") # Mais espaçamento
            # Botão para gerar novo jogo
            if st.button("Gerar Novo Jogo"):
                if st.session_state['most_common'] and st.session_state['least_common']:
                    st.session_state['suggested_game'] = suggest_numbers(
                        st.session_state['most_common'], 
                        st.session_state['least_common'], 
                        st.session_state['num_dezenas_to_play']
                    )
                else:
                    st.warning("Por favor, clique em 'Buscar Últimos Resultados' primeiro para carregar os dados de análise.")
                # O clique no botão já força um rerun, então não precisamos de st.rerun() explícito aqui
                
        st.subheader(f"Seu Jogo Sugerido ({st.session_state['num_dezenas_to_play']} dezenas):")
        if st.session_state['suggested_game']:
            # Exibe os números sugeridos de forma visual
            formatted_numbers = " ".join([f"**{num:02d}**" for num in st.session_state['suggested_game']]) 
            st.markdown(f"### {formatted_numbers}")
            st.write("Esta sugestão tenta combinar números quentes, frios e aleatórios para diversificar.")
        else:
            st.info("Clique em 'Buscar Últimos Resultados' ou 'Gerar Novo Jogo' para ter uma sugestão de aposta.")

        # Exibe o preço
        selected_price = MEGA_SENA_PRICES.get(st.session_state['num_dezenas_to_play'], "N/A")
        if selected_price != "N/A":
            st.markdown(f"**Valor estimado do jogo:** R$ {selected_price:.2f}")
        else:
            st.warning(f"Valor para {st.session_state['num_dezenas_to_play']} dezenas não disponível na tabela de preços.")

        st.subheader("Valores dos Jogos da Mega Sena")
        st.write("Consulte a tabela abaixo para saber o valor da aposta de acordo com a quantidade de números jogados:")
        
        prices_df = pd.DataFrame(MEGA_SENA_PRICES.items(), columns=['Números Jogados', 'Valor (R$)'])
        st.dataframe(prices_df.style.format({'Valor (R$)': 'R$ {:.2f}'}))
        st.info("Os valores podem ser atualizados pela Caixa Econômica Federal. Consulte sempre as informações oficiais.")

        st.markdown("---")

        st.info("""
        **Observação Importante:** Esta análise é apenas para fins informativos e estatísticos.
        Resultados passados não influenciam sorteios futuros, pois cada sorteio é um evento independente e aleatório.
        Jogue com responsabilidade.
        """)
    else:
        st.info("Clique no botão '📊 Buscar Últimos Resultados' acima para iniciar a análise e obter sugestões de jogo.")


if __name__ == "__main__":
    main()
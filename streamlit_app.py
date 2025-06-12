import streamlit as st
from datetime import date, datetime, timedelta
import calendar
import hashlib
import time
from streamlit_js_eval import streamlit_js_eval

# Classe Funcionario embutida no mesmo arquivo
class Funcionario:
    _funcionarios = {}  # Simula um banco de dados em memória

    def __init__(self, id, nome, coren, cargo, tipo_vinculo, data_admissao, gerente=False, turno=None, local=None):
        self.id = id
        self.nome = nome
        self.coren = coren
        self.cargo = cargo
        self.tipo_vinculo = tipo_vinculo
        self.data_admissao = data_admissao
        self.gerente = gerente
        self.turno = turno
        self.local = local
        self._senha_hash = None
        self.folgas = []  # Lista de tuplas (data_inicio, data_fim)

    def set_senha(self, senha):
        self._senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    def checa_senha(self, senha):
        return self._senha_hash == hashlib.sha256(senha.encode()).hexdigest()

    def save(self):
        try:
            Funcionario._funcionarios[self.id] = self
            if "funcionarios_state" not in st.session_state:
                st.session_state["funcionarios_state"] = {}
            st.session_state["funcionarios_state"][self.id] = self
        except Exception as e:
            st.error(f"DEBUG: Erro ao salvar funcionário: {str(e)}")
            raise

    @classmethod
    def get_funcionario_por_id(cls, id):
        if "funcionarios_state" in st.session_state:
            cls._funcionarios = st.session_state["funcionarios_state"]
        return cls._funcionarios.get(id)

    @classmethod
    def buscar_por_nome(cls, nome):
        if "funcionarios_state" in st.session_state:
            cls._funcionarios = st.session_state["funcionarios_state"]
        nome = nome.strip().lower()
        return [f for f in cls._funcionarios.values() if f.nome.strip().lower().find(nome) != -1]

    @classmethod
    def buscar_por_dia(cls, dia, mes, ano, last_day_parity=None):
        if "funcionarios_state" in st.session_state:
            cls._funcionarios = st.session_state["funcionarios_state"]
        
        prestadores = []
        data_consulta = date(ano, mes, dia)

        for f in cls._funcionarios.values():
            if f.turno or any(data_inicio <= data_consulta <= data_fim for data_inicio, data_fim in f.folgas):
                 if not f.local:
                    f.local = "UH" # Garante local padrão
                 prestadores.append(f)
        return prestadores

# Inicializa o estado da sessão e atualiza tipo_vinculo automaticamente
def init_session():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["pagina"] = "login"
    if "funcionarios_state" not in st.session_state:
        st.session_state["funcionarios_state"] = {}
    
    Funcionario._funcionarios = st.session_state["funcionarios_state"]
    
    # Atualizar automaticamente AJ para FT após 7 dias
    hoje = date.today()
    for funcionario in Funcionario._funcionarios.values():
        if funcionario.tipo_vinculo == "AJ - PROGRAMA ANJO":
            dias_desde_admissao = (hoje - funcionario.data_admissao).days
            if dias_desde_admissao >= 7:
                funcionario.tipo_vinculo = "FT - EFETIVADO"
                funcionario.save()

# Tela de login
def login_screen():
    st.title("Pequeno Cotolengo - Login")
    
    with st.form("login_form"):
        coren = st.text_input("COREN", value="56.127")
        senha = st.text_input("Senha", type="password", value="147258")
        submitted = st.form_submit_button("Entrar")
        
        if submitted:
            if not coren or not senha:
                st.error("Por favor, preencha todos os campos.")
                return
            
            # Garante que o usuário gerente padrão exista
            if not Funcionario.get_funcionario_por_id("56.127"):
                gerente = Funcionario("56.127", "Gerente Padrão", "56.127", "gerente", "FT - EFETIVADO", date.today(), gerente=True)
                gerente.set_senha("147258")
                gerente.save()

            with st.spinner("Verificando credenciais..."):
                funcionario = Funcionario.get_funcionario_por_id(coren)
                if funcionario and funcionario.checa_senha(senha):
                    if funcionario.cargo.lower() in ["gerente", "supervisor"]:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario"] = {
                            "id": funcionario.id, "nome": funcionario.nome, "coren": funcionario.coren,
                            "cargo": funcionario.cargo, "gerente": funcionario.gerente
                        }
                        st.session_state["pagina"] = "menu"
                        st.rerun()
                    else:
                        st.error("Apenas gerente ou supervisor têm acesso.")
                else:
                    st.error("COREN ou senha inválidos.")

# Tela para adicionar novo supervisor
def adicionar_supervisor():
    st.header("Adicionar Novo Supervisor")
    with st.form("form_adicionar_supervisor"):
        coren = st.text_input("COREN do Supervisor", key="coren_supervisor")
        nome = st.text_input("Nome do Supervisor", key="nome_supervisor")
        senha = st.text_input("Senha", type="password", key="senha_supervisor")
        submitted = st.form_submit_button("Salvar Supervisor")
        
        if submitted:
            if not coren or not nome or not senha:
                st.warning("Por favor, preencha todos os campos obrigatórios.")
                return
            if Funcionario.get_funcionario_por_id(coren):
                st.error("Já existe um supervisor com esse COREN.")
                return
            novo = Funcionario(coren, nome, coren, "supervisor", "FT - EFETIVADO", date.today(), gerente=False)
            novo.set_senha(senha)
            novo.save()
            st.success("Supervisor cadastrado com sucesso!")
            time.sleep(1)
            st.session_state["pagina"] = "menu"
            st.rerun()

# Tela para adicionar novo prestador
def adicionar_prestador():
    st.header("Adicionar Novo Prestador de Serviço")
    with st.form("form_adicionar_prestador"):
        nome = st.text_input("Nome completo", key="nome_prestador")
        mat = st.text_input("Matrícula (MAT)", key="mat_prestador")
        coren = st.text_input("COREN", key="coren_prestador")
        cargo = st.text_input("Cargo", key="cargo_prestador")
        data_admissao = st.date_input("Data de admissão", value=date.today(), key="data_prestador")
        tipo_vinculo = st.selectbox(
            "Tipo de vínculo", ["AJ - PROGRAMA ANJO", "FT - EFETIVADO"], key="vinculo_prestador")
        salvar = st.form_submit_button("Salvar")

    if salvar:
        if not nome or not mat or not coren or not cargo:
            st.warning("Por favor, preencha todos os campos obrigatórios.")
            return
        if Funcionario.get_funcionario_por_id(mat):
            st.error("Já existe um prestador com essa matrícula.")
            return
        novo = Funcionario(mat, nome, coren, cargo, tipo_vinculo, data_admissao, gerente=False)
        novo.save()
        st.success("Prestador cadastrado com sucesso!")
        time.sleep(1)
        st.session_state["pagina"] = "menu"
        st.rerun()

# Tela para gerenciar prestadores
def gerenciar_prestadores():
    st.header("Gerenciar Pessoas Já Cadastradas")
    
    nome_busca = st.text_input("Digite o nome do prestador para buscar", key="busca_prestador")
    if nome_busca:
        prestadores = Funcionario.buscar_por_nome(nome_busca)
        if not prestadores:
            st.warning("Nenhum prestador encontrado com esse nome.")
            return

        for prestador in prestadores:
            st.subheader(f"Prestador: {prestador.nome}")
            with st.expander("Ver/Editar Detalhes"):
                st.write(f"Matrícula: {prestador.id}")
                st.write(f"COREN: {prestador.coren}")
                st.write(f"Cargo: {prestador.cargo}")
                st.write(f"Tipo de Vínculo: {prestador.tipo_vinculo}")
                st.write(f"Data de Admissão: {prestador.data_admissao}")
                folgas_str = ', '.join([f'{inicio.strftime("%d/%m/%y")} a {fim.strftime("%d/%m/%y")}' for inicio, fim in prestador.folgas])
                st.write(f"Folgas: {folgas_str if prestador.folgas else 'Nenhuma'}")

                with st.form(f"form_agendamento_{prestador.id}"):
                    turno = st.selectbox("Turno", ["", "Dia 1", "Dia 2", "Noite 1", "Noite 2"], index= ["", "Dia 1", "Dia 2", "Noite 1", "Noite 2"].index(prestador.turno) if prestador.turno else 0, key=f"turno_{prestador.id}")
                    local = st.selectbox("Local", ["UH", "UCCI"], index=["UH", "UCCI"].index(prestador.local) if prestador.local else 0, key=f"local_{prestador.id}")
                    
                    st.subheader("Registrar Folga")
                    data_inicio_folga = st.date_input("Data de Início da Folga", key=f"folga_inicio_{prestador.id}")
                    data_fim_folga = st.date_input("Data de Fim da Folga", key=f"folga_fim_{prestador.id}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        salvar_agendamento = st.form_submit_button("Salvar Agendamento")
                    with col2:
                        registrar_folga = st.form_submit_button("Registrar Folga")
                    with col3:
                        excluir = st.form_submit_button("Excluir Prestador")

                    if salvar_agendamento:
                        prestador.turno = turno
                        prestador.local = local
                        prestador.save()
                        st.success(f"Agendamento atualizado para {prestador.nome}!")
                        st.rerun()

                    if registrar_folga:
                        if data_inicio_folga > data_fim_folga:
                            st.error("A data de início da folga deve ser anterior ou igual à data de fim.")
                        else:
                            prestador.folgas.append((data_inicio_folga, data_fim_folga))
                            prestador.save()
                            st.success(f"Folga registrada para {prestador.nome}!")
                            st.rerun()

                    if excluir:
                        if prestador.id in Funcionario._funcionarios:
                            del Funcionario._funcionarios[prestador.id]
                            if "funcionarios_state" in st.session_state and prestador.id in st.session_state["funcionarios_state"]:
                                del st.session_state["funcionarios_state"][prestador.id]
                            st.success(f"Prestador {prestador.nome} excluído com sucesso!")
                            st.rerun()

# --- NOVA FUNÇÃO DE VISUALIZAÇÃO GERAL OTIMIZADA ---
def visualizacao_geral():
    st.header("Visualização Geral dos Plantões")

    # CSS para controlar a impressão e estilizar a tabela
    print_and_style_css = """
    <style>
        .calendar-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: fixed; /* Força colunas de larguras iguais */
        }
        .calendar-table th, .calendar-table td {
            border: 1px solid #bbb;
            vertical-align: top;
            height: 160px; /* Altura das células */
            width: 14.28%; /* 100% / 7 dias */
            padding: 4px;
            overflow: hidden; /* Evita que o conteúdo transborde */
        }
        .calendar-table th {
            background-color: #343a40;
            color: white;
            text-align: center;
            font-size: 14px;
        }
        .calendar-table td .day-number {
            font-weight: bold;
            text-align: right;
            font-size: 16px;
            color: white;
            margin-bottom: 5px;
        }
        .calendar-table .empty-day {
            background-color: #f0f2f6;
        }
        .prestador-info {
            padding: 3px 5px; 
            margin: 3px 1px; 
            border-radius: 4px; 
            font-size: 12px; 
            color: #000000;
            line-height: 1.2;
        }
        .prestador-dia { background-color: #d1e7ff; }
        .prestador-noite { background-color: #ffd1dc; }
        .prestador-folga { background-color: #cccccc; text-decoration: line-through; }
        .turno-header { font-size: 10px; font-weight: bold; text-align: center; color: white; margin-top: 5px; }

        @media print {
            body { font-size: 9pt; }
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            
            /* Esconde elementos desnecessários */
            [data-testid="stSidebar"], [data-testid="stHeader"], .stButton {
                display: none !important;
            }
            /* Remove padding extra para usar a página toda */
            [data-testid="stAppViewContainer"], [data-testid="block-container"] {
                padding: 0 !important;
                margin: 0 !important;
            }
        }
    </style>
    """
    st.markdown(print_and_style_css, unsafe_allow_html=True)

    if st.button("Imprimir Tabela"):
        streamlit_js_eval(js_expressions="window.print()")

    # Lógica do Calendário para o Mês Atual
    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    st.markdown(f"### Calendário de {calendar.month_name[mes]} {ano}")
    
    html_calendario = "<table class='calendar-table'><thead><tr>"
    dias_da_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    for dia_semana in dias_da_semana:
        html_calendario += f"<th>{dia_semana}</th>"
    html_calendario += "</tr></thead><tbody>"

    last_day_current_month = calendar.monthrange(ano, mes)[1]
    last_day_parity = last_day_current_month % 2 == 0

    cal = calendar.monthcalendar(ano, mes)
    for semana in cal:
        html_calendario += "<tr>"
        for dia in semana:
            if dia == 0:
                html_calendario += "<td class='empty-day'></td>"
            else:
                html_calendario += "<td>"
                html_calendario += f"<div class='day-number'>{dia}</div>"
                
                # Lógica de paridade para o mês atual
                is_dia_par = dia % 2 == 0
                
                data_atual = date(ano, mes, dia)
                todos_prestadores = Funcionario.buscar_por_dia(dia, mes, ano)
                
                # Filtra por turno e folga
                em_folga = {p.id for p in todos_prestadores if any(f[0] <= data_atual <= f[1] for f in p.folgas)}
                
                dia1 = {p for p in todos_prestadores if p.turno == "Dia 1" and p.id not in em_folga}
                dia2 = {p for p in todos_prestadores if p.turno == "Dia 2" and p.id not in em_folga}
                noite1 = {p for p in todos_prestadores if p.turno == "Noite 1" and p.id not in em_folga}
                noite2 = {p for p in todos_prestadores if p.turno == "Noite 2" and p.id not in em_folga}
                
                plantao_dia = dia1 if not is_dia_par else dia2
                plantao_noite = noite1 if not is_dia_par else noite2

                # Renderiza HTML
                if plantao_dia:
                    html_calendario += "<div class='turno-header'>☀️ DIA</div>"
                    for p in sorted(list(plantao_dia), key=lambda x: x.nome):
                        sigla = "AJ" if p.tipo_vinculo == "AJ - PROGRAMA ANJO" else "FT"
                        html_calendario += f"<div class='prestador-info prestador-dia'>{p.nome} ({sigla} {p.local})</div>"
                
                if plantao_noite:
                    html_calendario += "<div class='turno-header'>🌙 NOITE</div>"
                    for p in sorted(list(plantao_noite), key=lambda x: x.nome):
                        sigla = "AJ" if p.tipo_vinculo == "AJ - PROGRAMA ANJO" else "FT"
                        html_calendario += f"<div class='prestador-info prestador-noite'>{p.nome} ({sigla} {p.local})</div>"
                
                if em_folga:
                    html_calendario += "<div class='turno-header'>🌴 FOLGA</div>"
                    for p_id in em_folga:
                        p = Funcionario.get_funcionario_por_id(p_id)
                        if p:
                            html_calendario += f"<div class='prestador-info prestador-folga'>{p.nome}</div>"
                            
                html_calendario += "</td>"
        html_calendario += "</tr>"
    html_calendario += "</tbody></table>"

    st.markdown(html_calendario, unsafe_allow_html=True)
    # A lógica para o próximo mês pode ser adicionada aqui, seguindo o mesmo padrão.

# Menu principal
def main_menu():
    st.sidebar.title(f"Bem-vindo(a), {st.session_state['usuario']['nome']}")
    
    opcoes = ["Visualização geral", "Gerenciar prestadores", "Adicionar novo prestador"]
    
    pagina = st.sidebar.radio("Selecione uma opção:", opcoes)
    
    if st.session_state["usuario"]["gerente"]:
        if st.sidebar.button("Adicionar Novo Supervisor"):
            st.session_state["pagina"] = "adicionar_supervisor"
            st.rerun()
    
    # Navegação principal
    if pagina == "Visualização geral":
        visualizacao_geral()
    elif pagina == "Gerenciar prestadores":
        gerenciar_prestadores()
    elif pagina == "Adicionar novo prestador":
        adicionar_prestador()

# Botão de logout
def logout_button():
    if st.sidebar.button("Sair"):
        # Limpa todo o session_state para um logout completo
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# Código principal
def main():
    st.set_page_config(page_title="Sistema Cotolengo", layout="wide")
    init_session()
    
    if not st.session_state.get("autenticado"):
        login_screen()
    elif st.session_state.get("pagina") == "adicionar_supervisor" and st.session_state.get("usuario", {}).get("gerente"):
        adicionar_supervisor()
        if st.sidebar.button("Voltar ao Menu"):
            st.session_state.pagina = "menu"
            st.rerun()
    else:
        logout_button()
        main_menu()

if __name__ == "__main__":
    main()

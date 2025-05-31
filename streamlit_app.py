import streamlit as st
from datetime import date, datetime
import calendar
import hashlib
import time

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
            st.write(f"DEBUG: Funcionário salvo com ID {self.id}. Total de funcionários: {len(Funcionario._funcionarios)}")
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
        st.write(f"DEBUG: Nomes no dicionário: {[f.nome for f in cls._funcionarios.values()]}")
        nome = nome.strip().lower()
        st.write(f"DEBUG: Termo de busca (após strip): '{nome}'")
        return [f for f in cls._funcionarios.values() if f.nome.strip().lower().find(nome) != -1]

    @classmethod
    def buscar_por_dia(cls, dia, mes, ano, last_day_parity=None):
        if "funcionarios_state" in st.session_state:
            cls._funcionarios = st.session_state["funcionarios_state"]
        # Filtrar prestadores com turno definido e corresponder à paridade do dia
        prestadores = []
        for f in cls._funcionarios.values():
            if f.turno:
                if last_day_parity is None:  # Mês atual
                    if (f.turno == "Dia 1" and dia % 2 == 1) or (f.turno == "Dia 2" and dia % 2 == 0) or \
                       (f.turno == "Noite 1" and dia % 2 == 1) or (f.turno == "Noite 2" and dia % 2 == 0):
                        prestadores.append(f)
                else:  # Próximo mês
                    if last_day_parity:  # Último dia par
                        if (f.turno == "Dia 2" and dia % 2 == 1) or (f.turno == "Dia 1" and dia % 2 == 0) or \
                           (f.turno == "Noite 2" and dia % 2 == 1) or (f.turno == "Noite 1" and dia % 2 == 0):
                            prestadores.append(f)
                    else:  # Último dia ímpar
                        if (f.turno == "Dia 1" and dia % 2 == 1) or (f.turno == "Dia 2" and dia % 2 == 0) or \
                           (f.turno == "Noite 1" and dia % 2 == 1) or (f.turno == "Noite 2" and dia % 2 == 0):
                            prestadores.append(f)
            if not f.local:
                f.local = "UH"
        return prestadores

# Inicializa o estado da sessão
def init_session():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["pagina"] = "login"
    if "funcionarios_state" not in st.session_state:
        st.session_state["funcionarios_state"] = {}
    Funcionario._funcionarios = st.session_state["funcionarios_state"]

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
                
            with st.spinner("Verificando credenciais..."):
                try:
                    funcionario = Funcionario.get_funcionario_por_id(coren)
                    if not funcionario:
                        gerente = Funcionario("56.127", "Gerente Padrão", "56.127", "gerente", "FT - EFETIVADO", date.today(), gerente=True)
                        gerente.set_senha("147258")
                        gerente.save()
                        funcionario = gerente
                    if funcionario and funcionario.checa_senha(senha):
                        if funcionario.cargo.lower() in ["gerente", "supervisor"]:
                            st.session_state["autenticado"] = True
                            st.session_state["usuario"] = {
                                "id": funcionario.id,
                                "nome": funcionario.nome,
                                "coren": funcionario.coren,
                                "cargo": funcionario.cargo,
                                "gerente": funcionario.gerente
                            }
                            st.session_state["pagina"] = "menu"
                            st.success(f"Bem-vindo(a), {funcionario.nome}!")
                        else:
                            st.error("Apenas gerente ou supervisor têm acesso.")
                    else:
                        st.error("COREN ou senha inválidos.")
                except Exception as e:
                    st.error(f"Erro ao autenticar: {str(e)}")

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

            try:
                existente = Funcionario.get_funcionario_por_id(coren)
                if existente:
                    st.error("Já existe um supervisor com esse COREN.")
                    return

                novo = Funcionario(coren, nome, coren, "supervisor", "FT - EFETIVADO", date.today(), gerente=False)
                novo.set_senha(senha)
                novo.save()
                st.success("Supervisor cadastrado com sucesso!")
                time.sleep(1)
                st.session_state["pagina"] = "menu"
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao cadastrar supervisor: {str(e)}")

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
            "Tipo de vínculo",
            ["AJ - PROGRAMA ANJO", "FT - EFETIVADO"],
            key="vinculo_prestador"
        )
        salvar = st.form_submit_button("Salvar")

    if salvar:
        if not nome or not mat or not coren or not cargo:
            st.warning("Por favor, preencha todos os campos obrigatórios.")
            return

        try:
            st.write(f"DEBUG: Tentando adicionar prestador - Nome: {nome}, MAT: {mat}, COREN: {coren}")
            existente = Funcionario.get_funcionario_por_id(mat)
            if existente:
                st.error("Já existe um prestador com essa matrícula.")
                return

            novo = Funcionario(mat, nome, coren, cargo, tipo_vinculo, data_admissao, gerente=False)
            novo.save()

            if mat in Funcionario._funcionarios:
                st.success("Prestador cadastrado com sucesso!")
                time.sleep(1)
                st.session_state["pagina"] = "menu"
                st.rerun()
            else:
                st.error("Falha ao salvar o prestador. O funcionário não foi encontrado no dicionário.")
        except Exception as e:
            st.error(f"Erro ao cadastrar prestador: {str(e)}")

# Tela para gerenciar prestadores
def gerenciar_prestadores():
    st.header("Gerenciar Pessoas Já Cadastradas")
    
    nome_busca = st.text_input("Digite o nome do prestador para buscar", key="busca_prestador")
    if nome_busca:
        try:
            prestadores = Funcionario.buscar_por_nome(nome_busca)
            st.write(f"DEBUG: Prestadores encontrados: {len(prestadores)}")
            st.write(f"DEBUG: Funcionários no dicionário: {len(Funcionario._funcionarios)}")
            if not prestadores:
                st.warning("Nenhum prestador encontrado com esse nome.")
                return

            for prestador in prestadores:
                st.subheader(f"Prestador: {prestador.nome}")
                st.write(f"Matrícula: {prestador.id}")
                st.write(f"COREN: {prestador.coren}")
                st.write(f"Cargo: {prestador.cargo}")
                st.write(f"Tipo de Vínculo: {prestador.tipo_vinculo}")
                st.write(f"Data de Admissão: {prestador.data_admissao}")

                with st.form(f"form_agendamento_{prestador.id}"):
                    turno = st.selectbox(
                        "Turno",
                        ["Dia 1", "Dia 2", "Noite 1", "Noite 2"],
                        key=f"turno_{prestador.id}"
                    )
                    local = st.selectbox(
                        "Local",
                        ["UH", "UCCI"],
                        key=f"local_{prestador.id}"
                    )
                    salvar_agendamento = st.form_submit_button("Salvar Agendamento")

                    if salvar_agendamento:
                        prestador.turno = turno
                        prestador.local = local
                        prestador.save()
                        st.success(f"Agendamento atualizado para {prestador.nome}!")
                        time.sleep(1)
                        st.session_state["pagina"] = "menu"
                        st.rerun()
        except Exception as e:
            st.error(f"Erro ao buscar prestadores: {str(e)}")

# Tela de visualização geral
def visualizacao_geral():
    st.header("Visualização Geral dos Plantões")
    
    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    cal = calendar.monthcalendar(ano, mes)
    dias_da_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

    # Determinar o último dia do mês atual e sua paridade
    last_day = calendar.monthrange(ano, mes)[1]
    last_day_parity = last_day % 2 == 0  # True se par, False se ímpar

    # Cabeçalho do calendário com dias da semana
    st.markdown(f"### Calendário de {calendar.month_name[mes]} {ano}")
    header_cols = st.columns(7)
    for i, dia_semana in enumerate(dias_da_semana):
        with header_cols[i]:
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>{dia_semana}</div>", unsafe_allow_html=True)

    # Grade do calendário
    for semana in cal:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                if dia == 0:
                    st.markdown("<div style='border: 1px solid #ddd; padding: 5px; min-height: 50px; background-color: #f0f0f0;'></div>", unsafe_allow_html=True)
                else:
                    # Buscar prestadores agendados para o dia
                    prestadores = Funcionario.buscar_por_dia(dia, mes, ano, last_day_parity)
                    cell_content = f"<div style='border: 1px solid #ddd; padding: 5px; min-height: 50px; background-color: #ffffff;'>"
                    cell_content += f"<div style='font-weight: bold; text-align: center;'>{dia}</div>"
                    try:
                        if prestadores:
                            for p in prestadores:
                                turno_atribuido = p.turno
                                horario = "7h às 19h" if "Dia" in turno_atribuido else "19h às 7h"
                                bg_color = "#d4edda" if "1" in turno_atribuido else "#f8d7da"
                                cell_content += (
                                    f"<div style='background-color: {bg_color}; padding: 2px; margin: 2px; border-radius: 3px; text-align: center; font-size: 12px;'>"
                                    f"{p.nome} ({p.id})<br>Turno: {turno_atribuido} ({horario})"
                                    f"</div>"
                                )
                        else:
                            cell_content += "<div style='color: #888; font-style: italic; text-align: center; font-size: 12px;'>Nenhum plantão</div>"
                    except Exception as e:
                        cell_content += f"<div style='color: red; text-align: center; font-size: 12px;'>Erro: {str(e)}</div>"
                    cell_content += "</div>"
                    st.markdown(cell_content, unsafe_allow_html=True)

    # Visualização do próximo mês (resumo)
    next_month = mes + 1 if mes < 12 else 1
    next_year = ano + 1 if mes == 12 else ano
    next_cal = calendar.monthcalendar(next_year, next_month)
    st.markdown(f"### Previsão para {calendar.month_name[next_month]} {next_year}")
    header_cols_next = st.columns(7)
    for i, dia_semana in enumerate(dias_da_semana):
        with header_cols_next[i]:
            st.markdown(f"<div style='text-align: center; font-weight: bold;'>{dia_semana}</div>", unsafe_allow_html=True)

    for semana in next_cal:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                if dia == 0:
                    st.markdown("<div style='border: 1px solid #ddd; padding: 5px; min-height: 50px; background-color: #f0f0f0;'></div>", unsafe_allow_html=True)
                else:
                    prestadores = Funcionario.buscar_por_dia(dia, next_month, next_year, last_day_parity)
                    cell_content = f"<div style='border: 1px solid #ddd; padding: 5px; min-height: 50px; background-color: #ffffff;'>"
                    cell_content += f"<div style='font-weight: bold; text-align: center;'>{dia}</div>"
                    try:
                        if prestadores:
                            for p in prestadores:
                                turno_atribuido = p.turno
                                horario = "7h às 19h" if "Dia" in turno_atribuido else "19h às 7h"
                                bg_color = "#d4edda" if "1" in turno_atribuido else "#f8d7da"
                                cell_content += (
                                    f"<div style='background-color: {bg_color}; padding: 2px; margin: 2px; border-radius: 3px; text-align: center; font-size: 12px;'>"
                                    f"{p.nome} ({p.id})<br>Turno: {turno_atribuido} ({horario})"
                                    f"</div>"
                                )
                        else:
                            cell_content += "<div style='color: #888; font-style: italic; text-align: center; font-size: 12px;'>Nenhum plantão</div>"
                    except Exception as e:
                        cell_content += f"<div style='color: red; text-align: center; font-size: 12px;'>Erro: {str(e)}</div>"
                    cell_content += "</div>"
                    st.markdown(cell_content, unsafe_allow_html=True)

# Menu principal
def main_menu():
    st.sidebar.title(f"Bem-vindo(a), {st.session_state['usuario']['nome']}")
    
    pagina = st.sidebar.radio(
        "Selecione uma opção:",
        ["Adicionar novo prestador", "Gerenciar prestadores", "Visualização geral"]
    )
    
    if st.session_state["usuario"]["gerente"]:
        if st.sidebar.button("Novo Registro (Supervisor)"):
            st.session_state["pagina"] = "adicionar_supervisor"
            st.rerun()
    
    st.session_state["pagina"] = pagina
    
    if pagina == "Adicionar novo prestador":
        adicionar_prestador()
    elif pagina == "Gerenciar prestadores":
        gerenciar_prestadores()
    elif pagina == "Visualização geral":
        visualizacao_geral()

# Botão de logout
def logout_button():
    if st.sidebar.button("Sair"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["pagina"] = "login"
        st.rerun()

# Código principal
def main():
    st.set_page_config(page_title="Sistema Cotolengo", layout="wide")
    init_session()
    
    if not st.session_state["autenticado"]:
        login_screen()
    elif st.session_state["pagina"] == "adicionar_supervisor" and st.session_state["usuario"]["gerente"]:
        adicionar_supervisor()
    else:
        logout_button()
        main_menu()

if __name__ == "__main__":
    main()

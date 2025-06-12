import streamlit as st
from datetime import date, datetime, timedelta
import calendar
import hashlib
import time
from streamlit_js_eval import streamlit_js_eval

# --- CLASSE FUNCIONARIO E DEMAIS FUNÇÕES (SEM ALTERAÇÃO) ---
class Funcionario:
    _funcionarios = {}
    def __init__(self, id, nome, coren, cargo, tipo_vinculo, data_admissao, gerente=False, turno=None, local=None):
        self.id, self.nome, self.coren, self.cargo, self.tipo_vinculo, self.data_admissao, self.gerente, self.turno, self.local = id, nome, coren, cargo, tipo_vinculo, data_admissao, gerente, turno, local
        self._senha_hash, self.folgas = None, []
    def set_senha(self, senha): self._senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    def checa_senha(self, senha): return self._senha_hash == hashlib.sha256(senha.encode()).hexdigest()
    def save(self):
        Funcionario._funcionarios[self.id] = self
        if "funcionarios_state" not in st.session_state: st.session_state["funcionarios_state"] = {}
        st.session_state["funcionarios_state"][self.id] = self
    @classmethod
    def get_funcionario_por_id(cls, id):
        if "funcionarios_state" in st.session_state: cls._funcionarios = st.session_state["funcionarios_state"]
        return cls._funcionarios.get(id)
    @classmethod
    def buscar_por_nome(cls, nome):
        if "funcionarios_state" in st.session_state: cls._funcionarios = st.session_state["funcionarios_state"]
        return [f for f in cls._funcionarios.values() if nome.strip().lower() in f.nome.strip().lower()]
    @classmethod
    def buscar_por_dia(cls, dia, mes, ano):
        if "funcionarios_state" in st.session_state: cls._funcionarios = st.session_state["funcionarios_state"]
        data_consulta, prestadores = date(ano, mes, dia), []
        for f in cls._funcionarios.values():
            if f.turno or any(i <= data_consulta <= f_ for i, f_ in f.folgas):
                if not f.local: f.local = "UH"
                prestadores.append(f)
        return prestadores

def init_session():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado, st.session_state.usuario, st.session_state.pagina = False, None, "login"
    if "funcionarios_state" not in st.session_state: st.session_state.funcionarios_state = {}
    Funcionario._funcionarios = st.session_state.funcionarios_state
    hoje = date.today()
    for f in list(Funcionario._funcionarios.values()):
        if f.tipo_vinculo == "AJ - PROGRAMA ANJO" and (hoje - f.data_admissao).days >= 7:
            # --- LINHA CORRIGIDA AQUI ---
            f.tipo_vinculo = "FT - EFETIVADO"
            f.save()
            # --------------------------

def login_screen():
    st.title("Pequeno Cotolengo - Login")
    with st.form("login_form"):
        coren, senha = st.text_input("COREN", "56.127"), st.text_input("Senha", "147258", type="password")
        if st.form_submit_button("Entrar"):
            if not Funcionario.get_funcionario_por_id("56.127"):
                gerente = Funcionario("56.127", "Gerente Padrão", "56.127", "gerente", "FT - EFETIVADO", date.today(), True)
                gerente.set_senha("147258"); gerente.save()
            f = Funcionario.get_funcionario_por_id(coren)
            if f and f.checa_senha(senha) and f.cargo.lower() in ["gerente", "supervisor"]:
                st.session_state.autenticado, st.session_state.usuario = True, {"id": f.id, "nome": f.nome, "gerente": f.gerente}
                st.rerun()
            else: st.error("Credenciais inválidas ou sem permissão de acesso.")

def adicionar_supervisor():
    st.header("Adicionar Novo Supervisor")
    with st.form("form_adicionar_supervisor"):
        coren = st.text_input("COREN do Supervisor")
        nome = st.text_input("Nome do Supervisor")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Salvar Supervisor"):
            if not all([coren, nome, senha]):
                st.warning("Preencha todos os campos.")
            elif Funcionario.get_funcionario_por_id(coren):
                st.error("Já existe um supervisor com esse COREN.")
            else:
                novo = Funcionario(coren, nome, coren, "supervisor", "FT - EFETIVADO", date.today(), False)
                novo.set_senha(senha)
                novo.save()
                st.success("Supervisor cadastrado!")
                time.sleep(1)
                st.rerun()

def adicionar_prestador():
    st.header("Adicionar Novo Prestador de Serviço")
    with st.form("form_adicionar_prestador"):
        nome = st.text_input("Nome completo")
        mat = st.text_input("Matrícula (MAT)")
        coren = st.text_input("COREN")
        cargo = st.text_input("Cargo")
        data_admissao = st.date_input("Data de admissão", date.today())
        tipo_vinculo = st.selectbox("Tipo de vínculo", ["AJ - PROGRAMA ANJO", "FT - EFETIVADO"])
        if st.form_submit_button("Salvar"):
            if not all([nome, mat, coren, cargo]):
                st.warning("Preencha todos os campos.")
            elif Funcionario.get_funcionario_por_id(mat):
                st.error("Já existe um prestador com essa matrícula.")
            else:
                novo = Funcionario(mat, nome, coren, cargo, tipo_vinculo, data_admissao, False)
                novo.save()
                st.success("Prestador cadastrado!")
                time.sleep(1)
                st.rerun()

def gerenciar_prestadores():
    st.header("Gerenciar Pessoas Já Cadastradas")
    nome_busca = st.text_input("Digite o nome para buscar")
    if nome_busca:
        prestadores = Funcionario.buscar_por_nome(nome_busca)
        if not prestadores: st.warning("Nenhum prestador encontrado.")
        for p in prestadores:
            st.subheader(f"Editando: {p.nome}")
            with st.expander("Ver/Editar Detalhes", expanded=True):
                with st.form(f"form_{p.id}"):
                    p.nome = st.text_input("Nome", p.nome, key=f"nome_{p.id}")
                    # Adicione outros campos para edição se necessário
                    st.form_submit_button("Salvar Alterações")
                # Lógica de turno, folga, etc. pode ser adicionada aqui
                st.write(f"Turno atual: {p.turno or 'Não definido'}")


def visualizacao_geral():
    st.header("Visualização Geral dos Plantões")

    print_css = """
    <style>
        #print-view { display: none; }
        @media print {
            body * { visibility: hidden; }
            #print-view, #print-view * { visibility: visible; }
            #print-view { position: absolute; left: 0; top: 0; width: 100%; }
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }
    </style>
    """
    st.markdown(print_css, unsafe_allow_html=True)

    if st.button("Imprimir Tabela"):
        streamlit_js_eval(js_expressions="window.print()")

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month

    def gerar_html_calendario():
        style_header = "background-color:#343a40 !important; color:white !important; text-align:center; padding:5px; border:1px solid #bbb;"
        style_cell = "vertical-align:top; height:160px; border:1px solid #bbb; padding:4px;"
        style_day_number = "font-weight:bold; text-align:right; font-size:16px; color:#333 !important;"
        style_turno_header = "font-size:10px; font-weight:bold; text-align:center; margin-top:5px; color:#000 !important;"
        
        html = f"<table style='width:100%; border-collapse:collapse;'><thead><tr>"
        for dia_semana in ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]:
            html += f"<th style='{style_header}'>{dia_semana}</th>"
        html += "</tr></thead><tbody>"

        cal = calendar.monthcalendar(ano, mes)
        for semana in cal:
            html += "<tr>"
            for dia in semana:
                if dia == 0:
                    html += f"<td style='{style_cell} background-color:#f0f2f6;'></td>"
                else:
                    html += f"<td style='{style_cell}'>"
                    html += f"<div style='{style_day_number}'>{dia}</div>"
                    
                    data_atual = date(ano, mes, dia)
                    prestadores = Funcionario.buscar_por_dia(dia, mes, ano)
                    
                    is_dia_par = dia % 2 == 0
                    em_folga_ids = {p.id for p in prestadores if any(f[0] <= data_atual <= f[1] for f in p.folgas)}
                    plantao_dia_ids = {p.id for p in prestadores if ((p.turno == "Dia 1" and not is_dia_par) or (p.turno == "Dia 2" and is_dia_par))} - em_folga_ids
                    plantao_noite_ids = {p.id for p in prestadores if ((p.turno == "Noite 1" and not is_dia_par) or (p.turno == "Noite 2" and is_dia_par))} - em_folga_ids

                    if plantao_dia_ids:
                        html += f"<div style='{style_turno_header}'>☀️ DIA</div>"
                        for p_id in sorted(list(plantao_dia_ids)):
                            p = Funcionario.get_funcionario_por_id(p_id)
                            cor = "background-color:#d1e7ff !important;"
                            html += f"<div style='{cor} padding:3px; margin:2px; border-radius:3px; font-size:11px; color:black !important;'>{p.nome}</div>"
                    if plantao_noite_ids:
                        html += f"<div style='{style_turno_header}'>🌙 NOITE</div>"
                        for p_id in sorted(list(plantao_noite_ids)):
                            p = Funcionario.get_funcionario_por_id(p_id)
                            cor = "background-color:#ffd1dc !important;"
                            html += f"<div style='{cor} padding:3px; margin:2px; border-radius:3px; font-size:11px; color:black !important;'>{p.nome}</div>"
                    if em_folga_ids:
                        html += f"<div style='{style_turno_header}'>🌴 FOLGA</div>"
                        for p_id in sorted(list(em_folga_ids)):
                            p = Funcionario.get_funcionario_por_id(p_id)
                            cor = "background-color:#cccccc !important; text-decoration:line-through;"
                            html += f"<div style='{cor} padding:3px; margin:2px; border-radius:3px; font-size:11px; color:black !important;'>{p.nome}</div>"

                    html += "</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html

    html_gerado = gerar_html_calendario()
    st.markdown(f"<div id='screen-view'>{html_gerado}</div>", unsafe_allow_html=True)
    st.markdown(f"<div id='print-view'>{html_gerado}</div>", unsafe_allow_html=True)

def main_menu():
    st.sidebar.title(f"Bem-vindo(a), {st.session_state['usuario']['nome']}")
    opcoes_base = ["Visualização geral", "Gerenciar prestadores", "Adicionar novo prestador"]
    if st.session_state["usuario"].get("gerente"):
        opcoes = opcoes_base + ["Adicionar Novo Supervisor"]
    else:
        opcoes = opcoes_base
    
    pagina = st.sidebar.radio("Selecione uma opção:", opcoes)

    if pagina == "Visualização geral": visualizacao_geral()
    elif pagina == "Gerenciar prestadores": gerenciar_prestadores()
    elif pagina == "Adicionar novo prestador": adicionar_prestador()
    elif pagina == "Adicionar Novo Supervisor": adicionar_supervisor()

def logout_button():
    if st.sidebar.button("Sair"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

def main():
    st.set_page_config(page_title="Sistema Cotolengo", layout="wide")
    if not st.session_state.get("autenticado"):
        login_screen()
    else:
        logout_button()
        main_menu()

if __name__ == "__main__":
    main()

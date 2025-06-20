import streamlit as st
from datetime import date, datetime, timedelta
import calendar
import hashlib
import time
from streamlit_js_eval import streamlit_js_eval
import sqlite3

# =============================================================================
# CONEXÃO COM O BANCO DE DADOS E INICIALIZAÇÃO
# AVISO: A persistência de dados a longo prazo (mais de 1 dia) requer
# a mudança para um banco de dados na nuvem (ex: Supabase, ElephantSQL, etc.).
# =============================================================================

def get_db_connection():
    conn = sqlite3.connect('cotolengo.db', check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id TEXT PRIMARY KEY, nome TEXT, coren TEXT, cargo TEXT, tipo_vinculo TEXT, data_admissao TEXT, gerente INTEGER, turno TEXT, local TEXT, senha_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS folgas 
                 (id_funcionario TEXT, data_inicio TEXT, data_fim TEXT, FOREIGN KEY(id_funcionario) REFERENCES funcionarios(id))''')
    conn.commit()
    conn.close()

# =============================================================================
# NOVA FUNÇÃO PARA INJETAR O SCRIPT DE IMPRESSÃO GLOBALMENTE
# =============================================================================
def inject_print_script():
    """ Injeta o JavaScript e CSS para impressão no início da aplicação. """
    st.markdown("""
    <script>
    // Função principal chamada pelo botão do Streamlit
    function printDiv(divId) {
        const printContents = document.getElementById(divId).innerHTML;
        const printWindow = window.open('', '', 'height=800,width=1000');
        
        printWindow.document.write('<html><head><title>Imprimir Escala</title>');
        // Estilos para a impressão
        printWindow.document.write(`
            <style>
                body { font-family: sans-serif; }
                table { width: 100%; border-collapse: collapse; }
                td, th { border: 1px solid #ccc; padding: 4px; text-align: center; }
                div { page-break-inside: avoid; } /* Evita quebras dentro dos 'cards' de nome */
            </style>
        `);
        printWindow.document.write('</head><body>');
        printWindow.document.write(printContents);
        printWindow.document.write('</body></html>');
        printWindow.document.close();

        // Adiciona um pequeno atraso para garantir que o conteúdo foi carregado
        setTimeout(function() {
            printWindow.print();
            printWindow.close();
        }, 500);
    }
    </script>
    """, unsafe_allow_html=True)


# --- O restante das suas classes e funções permanecem iguais ---

class Funcionario:
    _funcionarios = {}
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
        self.folgas = []
    def set_senha(self, senha):
        self._senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    def checa_senha(self, senha):
        return self._senha_hash == hashlib.sha256(senha.encode()).hexdigest()
    def save(self):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO funcionarios (id, nome, coren, cargo, tipo_vinculo, data_admissao, gerente, turno, local, senha_hash)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (self.id, self.nome, self.coren, self.cargo, self.tipo_vinculo, self.data_admissao.isoformat(),
                   1 if self.gerente else 0, self.turno, self.local, self._senha_hash))
        c.execute('DELETE FROM folgas WHERE id_funcionario = ?', (self.id,))
        for inicio, fim in self.folgas:
            c.execute('INSERT INTO folgas (id_funcionario, data_inicio, data_fim) VALUES (?, ?, ?)',
                      (self.id, inicio.isoformat(), fim.isoformat()))
        conn.commit()
        conn.close()
        Funcionario._funcionarios[self.id] = self
        if "funcionarios_state" not in st.session_state:
            st.session_state["funcionarios_state"] = {}
        st.session_state["funcionarios_state"][self.id] = self
    @classmethod
    def load_all(cls):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM funcionarios')
        for row in c.fetchall():
            f = cls(row[0], row[1], row[2], row[3], row[4], date.fromisoformat(row[5]), bool(row[6]), row[7], row[8])
            f._senha_hash = row[9]
            c.execute('SELECT data_inicio, data_fim FROM folgas WHERE id_funcionario = ?', (row[0],))
            f.folgas = [tuple(date.fromisoformat(x) for x in folga) for folga in c.fetchall()]
            cls._funcionarios[row[0]] = f
        conn.close()
        if "funcionarios_state" not in st.session_state:
            st.session_state["funcionarios_state"] = {}
        st.session_state["funcionarios_state"].update(cls._funcionarios)
    @classmethod
    def get_funcionario_por_id(cls, id):
        if not cls._funcionarios:
            cls.load_all()
        return cls._funcionarios.get(id)
    @classmethod
    def buscar_por_nome(cls, nome):
        if not cls._funcionarios:
            cls.load_all()
        nome = nome.strip().lower()
        return [f for f in cls._funcionarios.values() if f.nome.strip().lower().find(nome) != -1]
    @classmethod
    def buscar_por_dia(cls, dia, mes, ano, last_day_parity=None):
        if not cls._funcionarios:
            cls.load_all()
        prestadores = []
        data_consulta = date(ano, mes, dia)
        for f in cls._funcionarios.values():
            if f.turno:
                em_folga = any(data_inicio <= data_consulta <= data_fim for data_inicio, data_fim in f.folgas)
                if not em_folga:
                    if last_day_parity is None:
                        if (f.turno == "Dia 1" and dia % 2 == 1) or (f.turno == "Dia 2" and dia % 2 == 0) or \
                           (f.turno == "Noite 1" and dia % 2 == 1) or (f.turno == "Noite 2" and dia % 2 == 0):
                            prestadores.append(f)
                    else:
                        if last_day_parity:
                            if (f.turno == "Dia 2" and dia % 2 == 1) or (f.turno == "Dia 1" and dia % 2 == 0) or \
                               (f.turno == "Noite 2" and dia % 2 == 1) or (f.turno == "Noite 1" and dia % 2 == 0):
                                prestadores.append(f)
                        else:
                            if (f.turno == "Dia 1" and dia % 2 == 1) or (f.turno == "Dia 2" and dia % 2 == 0) or \
                               (f.turno == "Noite 1" and dia % 2 == 1) or (f.turno == "Noite 2" and dia % 2 == 0):
                                prestadores.append(f)
                else:
                    prestadores.append(f)
            if not f.local:
                f.local = "UH"
        return prestadores

def init_session():
    init_db()
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["pagina"] = "login"
    if "funcionarios_state" not in st.session_state:
        st.session_state["funcionarios_state"] = {}
    Funcionario._funcionarios = st.session_state.get("funcionarios_state", {})
    Funcionario.load_all()
    hoje = date.today()
    for funcionario in Funcionario._funcionarios.values():
        if funcionario.tipo_vinculo == "AJ - PROGRAMA ANJO":
            dias_desde_admissao = (hoje - funcionario.data_admissao).days
            if dias_desde_admissao >= 7:
                funcionario.tipo_vinculo = "FT - EFETIVADO"
                funcionario.save()

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
                            st.session_state["usuario"] = {"id": funcionario.id, "nome": funcionario.nome, "coren": funcionario.coren, "cargo": funcionario.cargo, "gerente": funcionario.gerente}
                            st.session_state["pagina"] = "menu"
                            st.rerun()
                        else:
                            st.error("Apenas gerente ou supervisor têm acesso.")
                    else:
                        st.error("COREN ou senha inválidos.")
                except Exception as e:
                    st.error(f"Erro ao autenticar: {str(e)}")

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
            except Exception as e:
                st.error(f"Erro ao cadastrar supervisor: {str(e)}")

def adicionar_prestador():
    st.header("Adicionar Novo Prestador de Serviço")
    with st.form("form_adicionar_prestador"):
        nome = st.text_input("Nome completo", key="nome_prestador")
        mat = st.text_input("Matrícula (MAT)", key="mat_prestador")
        coren = st.text_input("COREN", key="coren_prestador")
        cargo = st.text_input("Cargo", key="cargo_prestador")
        data_admissao = st.date_input("Data de admissão", value=date.today(), key="data_prestador")
        tipo_vinculo = st.selectbox("Tipo de vínculo", ["AJ - PROGRAMA ANJO", "FT - EFETIVADO"], key="vinculo_prestador")
        salvar = st.form_submit_button("Salvar")
    if salvar:
        if not nome or not mat or not coren or not cargo:
            st.warning("Por favor, preencha todos os campos obrigatórios.")
            return
        try:
            if Funcionario.get_funcionario_por_id(mat):
                st.error("Já existe um prestador com essa matrícula.")
                return
            novo = Funcionario(mat, nome, coren, cargo, tipo_vinculo, data_admissao, gerente=False)
            novo.save()
            st.success("Prestador cadastrado com sucesso!")
            time.sleep(1)
            st.session_state["pagina"] = "menu"
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao cadastrar prestador: {str(e)}")

def gerenciar_prestadores():
    st.header("Gerenciar Pessoas Já Cadastradas")
    nome_busca = st.text_input("Digite o nome do prestador para buscar", key="busca_prestador")
    if nome_busca:
        try:
            prestadores = Funcionario.buscar_por_nome(nome_busca)
            if not prestadores:
                st.warning("Nenhum prestador encontrado com esse nome.")
                return
            for prestador in prestadores:
                with st.container(border=True):
                    st.subheader(f"Prestador: {prestador.nome}")
                    cols = st.columns(3)
                    cols[0].write(f"**Matrícula:** {prestador.id}")
                    cols[1].write(f"**COREN:** {prestador.coren}")
                    cols[2].write(f"**Cargo:** {prestador.cargo}")
                    cols[0].write(f"**Vínculo:** {prestador.tipo_vinculo}")
                    cols[1].write(f"**Admissão:** {prestador.data_admissao.strftime('%d/%m/%Y')}")
                    folgas_str = ', '.join([f"{i.strftime('%d/%m')} a {f.strftime('%d/%m')}" for i, f in prestador.folgas]) if prestador.folgas else 'Nenhuma'
                    st.write(f"**Folgas:** {folgas_str}")
                    with st.form(f"form_agendamento_{prestador.id}"):
                        form_cols = st.columns(2)
                        with form_cols[0]:
                            turno = st.selectbox("Turno", ["Dia 1", "Dia 2", "Noite 1", "Noite 2"], key=f"turno_{prestador.id}", index=["Dia 1", "Dia 2", "Noite 1", "Noite 2"].index(prestador.turno) if prestador.turno else 0)
                            local = st.selectbox("Local", ["UH", "UCCI"], key=f"local_{prestador.id}", index=["UH", "UCCI"].index(prestador.local) if prestador.local else 0)
                        with form_cols[1]:
                            st.subheader("Registrar Folga")
                            data_inicio_folga = st.date_input("Início da Folga", key=f"folga_inicio_{prestador.id}")
                            data_fim_folga = st.date_input("Fim da Folga", key=f"folga_fim_{prestador.id}")
                        
                        btn_cols = st.columns(3)
                        if btn_cols[0].form_submit_button("Salvar Agendamento", use_container_width=True):
                            prestador.turno = turno
                            prestador.local = local
                            prestador.save()
                            st.success(f"Agendamento atualizado para {prestador.nome}!")
                            time.sleep(1); st.rerun()
                        if btn_cols[1].form_submit_button("Registrar Folga", use_container_width=True):
                            if data_inicio_folga > data_fim_folga:
                                st.error("A data de início da folga deve ser anterior ou igual à data de fim.")
                            else:
                                prestador.folgas.append((data_inicio_folga, data_fim_folga))
                                prestador.save()
                                st.success(f"Folga registrada para {prestador.nome}!"); time.sleep(1); st.rerun()
                        if btn_cols[2].form_submit_button("🗑️ Excluir Prestador", type="primary", use_container_width=True):
                            conn = get_db_connection(); c = conn.cursor()
                            c.execute('DELETE FROM folgas WHERE id_funcionario = ?', (prestador.id,)); c.execute('DELETE FROM funcionarios WHERE id = ?', (prestador.id,)); conn.commit(); conn.close()
                            if prestador.id in Funcionario._funcionarios: del Funcionario._funcionarios[prestador.id]
                            if "funcionarios_state" in st.session_state and prestador.id in st.session_state["funcionarios_state"]: del st.session_state["funcionarios_state"][prestador.id]
                            st.success(f"Prestador {prestador.nome} excluído!"); time.sleep(1); st.rerun()
        except Exception as e:
            st.error(f"Erro ao buscar prestadores: {str(e)}")

def visualizacao_geral():
    st.header("Visualização Geral dos Plantões")

    # Esta função não precisa mais do script de impressão, pois ele agora é global.

    def render_calendar_html(ano, mes, start_day, end_day):
        calendar.setfirstweekday(calendar.SUNDAY)
        dias_da_semana = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
        cal = calendar.monthcalendar(ano, mes)
        last_day_parity = calendar.monthrange(ano, mes)[1] % 2 == 0
        
        header_html = "".join([f"<th style='border: 1px solid #ccc; padding: 4px; text-align: center; font-size: 8pt; width: 14%;'>{d}</th>" for d in dias_da_semana])
        html = f"<table style='width: 100%; border-collapse: collapse;'><thead><tr>{header_html}</tr></thead><tbody>"

        for semana in cal:
            html += "<tr>"
            for dia in semana:
                if dia == 0 or not (start_day <= dia <= end_day):
                    html += "<td style='border: 1px solid #ccc; height: 100px;'></td>"
                    continue
                prestadores = Funcionario.buscar_por_dia(dia, mes, ano, last_day_parity)
                cell_content = f"<div style='font-weight: bold; text-align: center;'>{dia}</div>"
                prestadores_dia = sorted([p for p in prestadores if "Dia" in p.turno and not any(date(ano, mes, dia) >= di and date(ano, mes, dia) <= df for di, df in p.folgas)], key=lambda x: x.nome)
                prestadores_noite = sorted([p for p in prestadores if "Noite" in p.turno and not any(date(ano, mes, dia) >= di and date(ano, mes, dia) <= df for di, df in p.folgas)], key=lambda x: x.nome)
                folgas = sorted([p for p in prestadores if any(date(ano, mes, dia) >= di and date(ano, mes, dia) <= df for di, df in p.folgas)], key=lambda x: x.nome)
                if prestadores_dia:
                    cell_content += "<div style='font-size: 7pt; text-align: center; font-weight: bold; background-color: #e0e0e0;'>7h-19h</div>"
                    for p in prestadores_dia:
                        cell_content += f"<div style='font-size: 6pt; background-color: #d1e7ff; padding: 1px; margin-top: 1px; border-radius: 2px;'>{p.nome.split()[0]} - {p.local}</div>"
                if prestadores_noite:
                    cell_content += "<div style='font-size: 7pt; text-align: center; font-weight: bold; background-color: #e0e0e0;'>19h-7h</div>"
                    for p in prestadores_noite:
                        cell_content += f"<div style='font-size: 6pt; background-color: #ffd1dc; padding: 1px; margin-top: 1px; border-radius: 2px;'>{p.nome.split()[0]} - {p.local}</div>"
                if folgas:
                    cell_content += "<div style='font-size: 7pt; text-align: center; font-weight: bold; background-color: #e0e0e0;'>Folga</div>"
                    for p in folgas:
                        cell_content += f"<div style='font-size: 6pt; background-color: #f0f0f0; padding: 1px; margin-top: 1px; border-radius: 2px;'>{p.nome.split()[0]}</div>"
                html += f"<td style='border: 1px solid #ccc; vertical-align: top; padding: 2px;'>{cell_content}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    ultimo_dia_mes = calendar.monthrange(ano, mes)[1]
    
    tab1, tab2 = st.tabs(["1ª Quinzena (1-15)", "2ª Quinzena (16-Fim)"])

    with tab1:
        st.subheader(f"Escala de {calendar.month_name[mes]} {ano} - Dias 1 a 15")
        if st.button("🖨️ Imprimir 1ª Quinzena", key="btn_q1"):
            streamlit_js_eval(js_expressions="printDiv('quinzena1')")
        html_q1 = render_calendar_html(ano, mes, 1, 15)
        st.markdown(f"<div id='quinzena1'>{html_q1}</div>", unsafe_allow_html=True)
        
    with tab2:
        st.subheader(f"Escala de {calendar.month_name[mes]} {ano} - Dias 16 a {ultimo_dia_mes}")
        if st.button(f"🖨️ Imprimir 2ª Quinzena", key="btn_q2"):
            streamlit_js_eval(js_expressions="printDiv('quinzena2')")
        html_q2 = render_calendar_html(ano, mes, 16, ultimo_dia_mes)
        st.markdown(f"<div id='quinzena2'>{html_q2}</div>", unsafe_allow_html=True)

def main_menu():
    st.sidebar.title(f"Bem-vindo(a), {st.session_state['usuario']['nome']}")
    
    opcoes = ["Visualização geral", "Gerenciar prestadores", "Adicionar novo prestador"]
    if st.session_state["usuario"]["gerente"]:
        opcoes.append("Adicionar novo supervisor")

    pagina_selecionada = st.sidebar.radio("Selecione uma opção:", opcoes, key="menu_radio")
    
    # Navegação entre as páginas
    if pagina_selecionada == "Adicionar novo prestador":
        adicionar_prestador()
    elif pagina_selecionada == "Gerenciar prestadores":
        gerenciar_prestadores()
    elif pagina_selecionada == "Visualização geral":
        visualizacao_geral()
    elif pagina_selecionada == "Adicionar novo supervisor":
        adicionar_supervisor()

def logout_button():
    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()

def main():
    st.set_page_config(page_title="Sistema Cotolengo", layout="wide")
    
    # Injeta o script de impressão uma vez, no início.
    inject_print_script() 
    
    init_session()
    
    if not st.session_state.get("autenticado"):
        login_screen()
    else:
        logout_button()
        main_menu()

if __name__ == "__main__":
    main()

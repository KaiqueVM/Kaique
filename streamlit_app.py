import streamlit as st
from datetime import date, datetime, timedelta
import calendar
import hashlib
import time
import sqlite3

# Conexão com o banco de dados SQLite
def get_db_connection():
    conn = sqlite3.connect('cotolengo.db', check_same_thread=False)
    return conn

# Criar tabelas se não existirem
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                 (id TEXT PRIMARY KEY, nome TEXT, coren TEXT, cargo TEXT, tipo_vinculo TEXT, data_admissao TEXT, gerente INTEGER, turno TEXT, local TEXT, senha_hash TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS folgas 
                 (id_funcionario TEXT, data_inicio TEXT, data_fim TEXT, FOREIGN KEY(id_funcionario) REFERENCES funcionarios(id))''')
    conn.commit()
    conn.close()

# Classe Funcionario
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
        self.folgas = []  # Lista temporária para uso imediato

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
        # Remover folgas antigas do banco
        c.execute('DELETE FROM folgas WHERE id_funcionario = ?', (self.id,))
        # Salvar novas folgas
        for inicio, fim in self.folgas:
            c.execute('INSERT INTO folgas (id_funcionario, data_inicio, data_fim) VALUES (?, ?, ?)',
                      (self.id, inicio.isoformat(), fim.isoformat()))
        conn.commit()
        conn.close()
        Funcionario._funcionarios[self.id] = self
        if "funcionarios_state" not in st.session_state:
            st.session_state["funcionarios_state"] = {}
        st.session_state["funcionarios_state"][self.id] = self
        st.write(f"DEBUG: Funcionário salvo com ID {self.id}")

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

# Inicializa o estado da sessão e atualiza tipo_vinculo automaticamente
def init_session():
    init_db()
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["pagina"] = "login"
    if "funcionarios_state" not in st.session_state:
        st.session_state["funcionarios_state"] = {}
    Funcionario._funcionarios = st.session_state["funcionarios_state"]
    Funcionario.load_all()
    
    hoje = date.today()
    for funcionario in Funcionario._funcionarios.values():
        if funcionario.tipo_vinculo == "AJ - PROGRAMA ANJO":
            dias_desde_admissao = (hoje - funcionario.data_admissao).days
            if dias_desde_admissao >= 7:
                funcionario.tipo_vinculo = "FT - EFETIVADO"
                funcionario.save()
                st.write(f"DEBUG: Funcionário {funcionario.nome} movido de AJ para FT após {dias_desde_admissao} dias.")

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
                st.write(f"Folgas: {', '.join([f'{inicio} a {fim}' for inicio, fim in prestador.folgas]) if prestador.folgas else 'Nenhuma'}")

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
                    st.subheader("Registrar Folga")
                    data_inicio_folga = st.date_input("Data de Início da Folga", key=f"folga_inicio_{prestador.id}")
                    data_fim_folga = st.date_input("Data de Fim da Folga", key=f"folga_fim_{prestador.id}")
                    salvar_agendamento = st.form_submit_button("Salvar Agendamento")
                    registrar_folga = st.form_submit_button("Registrar Folga")
                    excluir = st.form_submit_button("Excluir Prestador")

                    if salvar_agendamento:
                        prestador.turno = turno
                        prestador.local = local
                        prestador.save()
                        st.success(f"Agendamento atualizado para {prestador.nome}!")
                        time.sleep(1)
                        st.session_state["pagina"] = "menu"
                        st.rerun()

                    if registrar_folga:
                        if data_inicio_folga > data_fim_folga:
                            st.error("A data de início da folga deve ser anterior ou igual à data de fim.")
                        else:
                            prestador.folgas.append((data_inicio_folga, data_fim_folga))
                            prestador.save()
                            st.success(f"Folga registrada para {prestador.nome} de {data_inicio_folga} a {data_fim_folga}!")
                            time.sleep(1)
                            st.rerun()

                    if excluir:
                        if prestador.id in Funcionario._funcionarios:
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute('DELETE FROM folgas WHERE id_funcionario = ?', (prestador.id,))
                            c.execute('DELETE FROM funcionarios WHERE id = ?', (prestador.id,))
                            conn.commit()
                            conn.close()
                            del Funcionario._funcionarios[prestador.id]
                            if "funcionarios_state" in st.session_state and prestador.id in st.session_state["funcionarios_state"]:
                                del st.session_state["funcionarios_state"][prestador.id]
                            st.success(f"Prestador {prestador.nome} excluído com sucesso!")
                            time.sleep(1)
                            st.session_state["pagina"] = "menu"
                            st.rerun()
        except Exception as e:
            st.error(f"Erro ao buscar prestadores: {str(e)}")

# Tela de visualização geral
def visualizacao_geral():
    st.header("Visualização Geral dos Plantões")
    
    # Adicionar CSS para impressão
    st.markdown("""
        <style>
        @media print {
            body, .stApp, .main, .block-container {
                background-color: white !important;
                color: black !important;
                width: 210mm !important;
                max-width: 210mm !important;
                height: 297mm !important;
                max-height: 297mm !important;
                margin: 0 !important;
                padding: 1mm !important;
                font-size: 6pt !important;
            }
            [data-testid="stSidebar"], .stButton, [data-testid="stToolbar"] {
                display: none !important;
            }
            .printable-content {
                display: flex !important;
                flex-wrap: wrap !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            .calendar-row {
                display: flex !important;
                width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            .calendar-cell {
                background-color: white !important;
                border: 1px solid black !important;
                color: black !important;
                padding: 1px !important;
                min-height: 40px !important;
                font-size: 6pt !important;
                width: 28mm !important;
                box-sizing: border-box !important;
                margin: 0 !important;
            }
            .calendar-cell-header {
                font-weight: bold !important;
                text-align: center !important;
                font-size: 7pt !important;
                color: black !important;
                padding: 1px !important;
                width: 28mm !important;
                box-sizing: border-box !important;
                margin: 0 !important;
            }
            .calendar-day {
                background-color: #e6f3ff !important;
                color: black !important;
                border: 1px solid #ccc !important;
                font-size: 5pt !important;
                padding: 1px !important;
                margin: 0 !important;
                border-radius: 1px !important;
                line-height: 1 !important;
            }
            .calendar-night {
                background-color: #ffe6ee !important;
                color: black !important;
                border: 1px solid #ccc !important;
                font-size: 5pt !important;
                padding: 1px !important;
                margin: 0 !important;
                border-radius: 1px !important;
                line-height: 1 !important;
            }
            .calendar-off {
                background-color: #f0f0f0 !important;
                color: black !important;
                border: 1px solid #ccc !important;
                font-size: 5pt !important;
                padding: 1px !important;
                margin: 0 !important;
                border-radius: 1px !important;
                line-height: 1 !important;
            }
            .calendar-empty {
                background-color: white !important;
                color: black !important;
                font-style: italic !important;
                font-size: 5pt !important;
                text-align: center !important;
            }
            .stMarkdown, .stHeader {
                page-break-inside: avoid !important;
            }
            /* Ajuste para colunas */
            .stColumn {
                width: 14.28% !important;
                max-width: 28mm !important;
                box-sizing: border-box !important;
                margin: 0 !important;
                padding: 0 !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # Instrução para impressão
    st.info("Para imprimir a tabela, pressione **Ctrl+P** (Windows) ou **Cmd+P** (Mac) no seu navegador.")

    hoje = datetime.today()
    ano, mes = hoje.year, hoje.month
    cal = calendar.monthcalendar(ano, mes)
    dias_da_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    last_day = calendar.monthrange(ano, mes)[1]
    last_day_parity = last_day % 2 == 0

    # Função auxiliar para renderizar o calendário
    def render_calendar(start_day, end_day):
        st.markdown(f"<div class='printable-content'><h3 style='font-size: 8pt;'>Calendário de {calendar.month_name[mes]} {ano} - Dias {start_day} a {end_day}</h3>", unsafe_allow_html=True)
        st.markdown("<div class='calendar-row'>", unsafe_allow_html=True)
        header_cols = st.columns(7)
        for i, dia_semana in enumerate(dias_da_semana):
            with header_cols[i]:
                st.markdown(f"<div class='calendar-cell-header'>{dia_semana}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        for semana in cal:
            st.markdown("<div class='calendar-row'>", unsafe_allow_html=True)
            cols = st.columns(7)
            for i, dia in enumerate(semana):
                with cols[i]:
                    if dia == 0 or dia < start_day or dia > end_day:
                        st.markdown("<div class='calendar-cell'></div>", unsafe_allow_html=True)
                    else:
                        prestadores = Funcionario.buscar_por_dia(dia, mes, ano, last_day_parity)
                        cell_content = f"<div class='calendar-cell'>"
                        cell_content += f"<div style='font-weight: bold; text-align: center; font-size: 7pt;'>{dia}</div>"
                        try:
                            if prestadores:
                                prestadores_dia = sorted([p for p in prestadores if "Dia" in p.turno and not any(date(ano, mes, dia) <= data_fim and date(ano, mes, dia) >= data_inicio for data_inicio, data_fim in p.folgas)], key=lambda x: x.nome)
                                prestadores_noite = sorted([p for p in prestadores if "Noite" in p.turno and not any(date(ano, mes, dia) <= data_fim and date(ano, mes, dia) >= data_inicio for data_inicio, data_fim in p.folgas)], key=lambda x: x.nome)
                                folgas_dia = sorted([p for p in prestadores if "Dia" in p.turno and any(date(ano, mes, dia) <= data_fim and date(ano, mes, dia) >= data_inicio for data_inicio, data_fim in p.folgas)], key=lambda x: x.nome)
                                folgas_noite = sorted([p for p in prestadores if "Noite" in p.turno and any(date(ano, mes, dia) <= data_fim and date(ano, mes, dia) >= data_inicio for data_inicio, data_fim in p.folgas)], key=lambda x: x.nome)

                                if prestadores_dia or folgas_dia:
                                    cell_content += "<div style='font-size: 5pt; font-weight: bold; text-align: center; margin-top: 1px;'>7h às 19h</div>"
                                    for p in prestadores_dia:
                                        sigla = "AJ" if p.tipo_vinculo == "AJ - PROGRAMA ANJO" else "FT"
                                        cell_content += f"<div class='calendar-day' style='font-size: 5pt;'>{p.nome} ({p.coren}), {p.cargo}, {sigla} {p.local}</div>"
                                    for p in folgas_dia:
                                        cell_content += f"<div class='calendar-off' style='font-size: 5pt;'>{p.nome} ({p.coren}), {p.cargo} (Folga)</div>"

                                if prestadores_noite or folgas_noite:
                                    cell_content += "<div style='font-size: 5pt; font-weight: bold; text-align: center; margin-top: 1px;'>19h às 7h</div>"
                                    for p in prestadores_noite:
                                        sigla = "AJ" if p.tipo_vinculo == "AJ - PROGRAMA ANJO" else "FT"
                                        cell_content += f"<div class='calendar-night' style='font-size: 5pt;'>{p.nome} ({p.coren}), {p.cargo}, {sigla} {p.local}</div>"
                                    for p in folgas_noite:
                                        cell_content += f"<div class='calendar-off' style='font-size: 5pt;'>{p.nome} ({p.coren}), {p.cargo} (Folga)</div>"
                            else:
                                cell_content += "<div class='calendar-empty' style='font-size: 5pt;'>Nenhum plantão</div>"
                        except Exception as e:
                            cell_content += f"<div style='color: red; text-align: center; font-size: 5pt;'>Erro: {str(e)}</div>"
                        cell_content += "</div>"
                        st.markdown(cell_content, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Abas para os períodos
    tab1, tab2 = st.tabs(["1ª Quinzena (1-15)", f"2ª Quinzena (16-{last_day})"])

    with tab1:
        render_calendar(1, 15)

    with tab2:
        render_calendar(16, last_day)

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

import sqlite3
import sys
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.image import Image
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from fpdf import FPDF
from kivy.core.window import Window




def conectar_db():
    try:
        conn = sqlite3.connect('controle_ferramentas.db')
        return conn
    except sqlite3.Error as e:
        print(f'Erro ao conectar ao banco de dados: {e}')
        sys.exit(1)


def criar_tabelas():
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS ferramentas (
            id TEXT PRIMARY KEY,
            batch TEXT NOT NULL,
            descricao TEXT NOT NULL,
            emprestada BOOLEAN NOT NULL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS tripulantes (
            re INTEGER PRIMARY KEY,
            nome TEXT NOT NULL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS emprestimos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ferramenta_id TEXT,
            tripulante_id INTEGER,
            acft TEXT NOT NULL,
            data_emprestimo TEXT,
            data_devolucao TEXT,
            FOREIGN KEY (ferramenta_id) REFERENCES ferramentas (id),
            FOREIGN KEY (tripulante_id) REFERENCES tripulantes (re))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS aeronaves (
            acft TEXT PRIMARY KEY,
            descricao TEXT NOT NULL)''')
        conn.commit()
    except sqlite3.Error as e:
        print(f'Erro ao criar tabelas: {e}')
    finally:
        conn.close()


criar_tabelas()

from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        # Logo
        self.image('logo.png', 10, 8, 33)  # Altere o caminho da imagem conforme necessário
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Comprovante de Empréstimo', 0, 1, 'C')
        self.ln(10)  # Adiciona uma linha em branco

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def gerar_comprovante(batch, re, acft, data_emprestimo):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Informações do empréstimo
    pdf.cell(0, 10, f"Batch: {batch}", ln=True)
    pdf.cell(0, 10, f"Tripulante RE: {re}", ln=True)
    pdf.cell(0, 10, f"Aeronave ACFT: {acft}", ln=True)
    pdf.cell(0, 10, f"Data do Empréstimo: {data_emprestimo}", ln=True)

    # Adicionando um espaço em branco
    pdf.ln(10)

    # Instruções adicionais
    pdf.cell(0, 10, "Instruções:", ln=True)
    pdf.multi_cell(0, 10, "Este comprovante deve ser apresentado na retirada do material e em caso de devolução. "
                           "Mantenha-o em lugar seguro.")

    # Salvar o PDF
    pdf_file = f'comprovante_emprestimo_{re}.pdf'
    pdf.output(pdf_file)

def registrar_emprestimo(batch, re, acft):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ferramentas WHERE batch = ? AND emprestada = 0", (batch,))
        ferramenta = cursor.fetchone()
        if not ferramenta:
            return f'Ferramenta com batch "{batch}" não disponível para empréstimo.'
        ferramenta_id = ferramenta[0]
        cursor.execute("SELECT re FROM tripulantes WHERE re = ?", (re,))
        tripulante = cursor.fetchone()
        if not tripulante:
            return f'Tripulante com RE "{re}" não encontrado.'
        cursor.execute("SELECT acft FROM aeronaves WHERE acft = ?", (acft,))
        aeronave = cursor.fetchone()
        if not aeronave:
            return f'Aeronave com ACFT "{acft}" não encontrada.'
        data_emprestimo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''INSERT INTO emprestimos (ferramenta_id, tripulante_id, acft, data_emprestimo)
                          VALUES (?, ?, ?, ?)''', (ferramenta_id, re, acft, data_emprestimo))
        cursor.execute('UPDATE ferramentas SET emprestada = 1 WHERE id = ?', (ferramenta_id,))
        conn.commit()

        # Gerar comprovante
        gerar_comprovante(batch, re, acft, data_emprestimo)

        # Abrir o arquivo PDF gerado
        abrir_comprovante(re)

        return f'Empréstimo registrado: Batch {batch} para o tripulante RE {re}, aeronave ACFT {acft}.'
    except sqlite3.Error as e:
        return f'Erro ao registrar empréstimo: {e}'
    finally:
        conn.close()


def abrir_comprovante(re):
    pdf_file = f'comprovante_emprestimo_{re}.pdf'
    try:
        os.startfile(pdf_file)  # Apenas para Windows
    except Exception as e:
        print(f'Erro ao abrir o arquivo PDF: {e}')



def devolver_ferramenta(batch):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ferramentas WHERE batch = ? AND emprestada = 1", (batch,))
        ferramenta = cursor.fetchone()
        if not ferramenta:
            return f'Ferramenta com batch "{batch}" não está emprestada.'
        ferramenta_id = ferramenta[0]
        cursor.execute('UPDATE ferramentas SET emprestada = 0 WHERE id = ?', (ferramenta_id,))
        cursor.execute('UPDATE emprestimos SET data_devolucao = ? WHERE ferramenta_id = ? AND data_devolucao IS NULL',
                       (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ferramenta_id))
        conn.commit()
        return f'Ferramenta com batch "{batch}" devolvida com sucesso!'
    except sqlite3.Error as e:
        return f'Erro ao devolver ferramenta: {e}'
    finally:
        conn.close()


def adicionar_tripulante(nome, re):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tripulantes (nome, re) VALUES (?, ?)', (nome, re))
        conn.commit()
        return f'Tripulante "{nome}" adicionado com sucesso!'
    except sqlite3.Error as e:
        return f'Erro ao adicionar tripulante: {e}'
    finally:
        conn.close()


def adicionar_ferramenta(batch, descricao):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO ferramentas (id, batch, descricao, emprestada) VALUES (?, ?, ?, ?)',
                       (batch, batch, descricao, 0))
        conn.commit()
        return f'Ferramenta "{descricao}" adicionada com sucesso!'
    except sqlite3.Error as e:
        return f'Erro ao adicionar ferramenta: {e}'
    finally:
        conn.close()


def adicionar_aeronave(acft, descricao):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO aeronaves (acft, descricao) VALUES (?, ?)', (acft, descricao))
        conn.commit()
        return f'Aeronave "{descricao}" adicionada com sucesso!'
    except sqlite3.Error as e:
        return f'Erro ao adicionar aeronave: {e}'
    finally:
        conn.close()


class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        layout = RelativeLayout()

        # Imagem de fundo
        self.bg_image = Image(source='azul_linhas_aereas.jpg', allow_stretch=True, keep_ratio=False)
        layout.add_widget(self.bg_image)

        # Layout principal
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Layout para os botões principais (categorias)
        categories_layout = GridLayout(cols=2, size_hint_y=None)
        categories_layout.bind(minimum_height=categories_layout.setter('height'))

        # Botões para categorias principais
        btns_info = [
            ("Tripulantes", self.abrir_tripulantes),
            ("Ferramentas", self.abrir_ferramentas),
            ("Aeronaves", self.abrir_aeronaves),
            ("Histórico", self.abrir_historico),
            ("Empréstimos", self.abrir_emprestimos),
            ("Devoluções", self.abrir_devolucoes)
        ]

        for btn_text, callback in btns_info:
            btn = Button(text=btn_text, size_hint_y=None, height=50,
                         background_color=(0, 0, 1, 1), color=(1, 1, 1, 1))
            btn.bind(on_release=callback)
            categories_layout.add_widget(btn)

        main_layout.add_widget(categories_layout)
        layout.add_widget(main_layout)
        self.add_widget(layout)

    def abrir_tripulantes(self, instance):
        self.manager.current = 'tripulantes'

    def abrir_ferramentas(self, instance):
        self.manager.current = 'ferramentas'

    def abrir_aeronaves(self, instance):
        self.manager.current = 'aeronaves'

    def abrir_historico(self, instance):
        self.manager.current = 'historico'

    def abrir_emprestimos(self, instance):
        self.manager.current = 'emprestimos'

    def abrir_devolucoes(self, instance):
        self.manager.current = 'devolucoes'


class TripulantesScreen(Screen):
    def __init__(self, **kwargs):
        super(TripulantesScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.nome_input = TextInput(hint_text="Nome do Tripulante", multiline=False)
        self.re_input = TextInput(hint_text="RE do Tripulante", multiline=False)
        adicionar_btn = Button(text="Adicionar Tripulante")
        adicionar_btn.bind(on_release=self.adicionar_tripulante)

        layout.add_widget(self.nome_input)
        layout.add_widget(self.re_input)
        layout.add_widget(adicionar_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def adicionar_tripulante(self, instance):
        nome = self.nome_input.text
        re = self.re_input.text
        if nome and re:
            result = adicionar_tripulante(nome, re)
            self.show_popup("Resultado", result)
            self.nome_input.text = ''
            self.re_input.text = ''
        else:
            self.show_popup("Erro", "Preencha todos os campos.")

    def voltar(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(None, None), size=(400, 200))
        popup.open()


class FerramentasScreen(Screen):
    def __init__(self, **kwargs):
        super(FerramentasScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.batch_input = TextInput(hint_text="Batch da Ferramenta", multiline=False)
        self.descricao_input = TextInput(hint_text="Descrição da Ferramenta", multiline=False)
        adicionar_btn = Button(text="Adicionar Ferramenta")
        adicionar_btn.bind(on_release=self.adicionar_ferramenta)

        layout.add_widget(self.batch_input)
        layout.add_widget(self.descricao_input)
        layout.add_widget(adicionar_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def adicionar_ferramenta(self, instance):
        batch = self.batch_input.text
        descricao = self.descricao_input.text
        if batch and descricao:
            result = adicionar_ferramenta(batch, descricao)
            self.show_popup("Resultado", result)
            self.batch_input.text = ''
            self.descricao_input.text = ''
        else:
            self.show_popup("Erro", "Preencha todos os campos.")

    def voltar(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(None, None), size=(400, 200))
        popup.open()


class AeronavesScreen(Screen):
    def __init__(self, **kwargs):
        super(AeronavesScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.acft_input = TextInput(hint_text="ACFT da Aeronave", multiline=False)
        self.descricao_input = TextInput(hint_text="Descrição da Aeronave", multiline=False)
        adicionar_btn = Button(text="Adicionar Aeronave")
        adicionar_btn.bind(on_release=self.adicionar_aeronave)

        layout.add_widget(self.acft_input)
        layout.add_widget(self.descricao_input)
        layout.add_widget(adicionar_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def adicionar_aeronave(self, instance):
        acft = self.acft_input.text
        descricao = self.descricao_input.text
        if acft and descricao:
            result = adicionar_aeronave(acft, descricao)
            self.show_popup("Resultado", result)
            self.acft_input.text = ''
            self.descricao_input.text = ''
        else:
            self.show_popup("Erro", "Preencha todos os campos.")

    def voltar(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(None, None), size=(400, 200))
        popup.open()


class HistoricoScreen(Screen):
    def __init__(self, **kwargs):
        super(HistoricoScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.historico_label = Label(text="Histórico de Empréstimos", size_hint_y=None, height=50)
        layout.add_widget(self.historico_label)

        self.scroll_view = ScrollView()
        self.historico_content = BoxLayout(orientation='vertical', size_hint_y=None)
        self.historico_content.bind(minimum_height=self.historico_content.setter('height'))

        self.atualizar_historico()

        self.scroll_view.add_widget(self.historico_content)
        layout.add_widget(self.scroll_view)

        self.atualizar_btn = Button(text="Atualizar Histórico", size_hint_y=None, height=50)
        self.atualizar_btn.bind(on_release=self.atualizar_historico)
        layout.add_widget(self.atualizar_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def atualizar_historico(self, instance=None):
        self.historico_content.clear_widgets()
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM emprestimos")
        for row in cursor.fetchall():
            status = "Devolvido" if row[5] else "Emprestado"  # data_devolucao é o sexto campo
            color = (0, 1, 0, 1) if row[5] else (1, 0, 0, 1)  # Verde se devolvido, vermelho se emprestado
            historico_label = Label(text=str(row), size_hint_y=None, height=40, color=color)
            self.historico_content.add_widget(historico_label)
        conn.close()

    def voltar(self, instance):
        self.manager.current = 'main'



class EmprestimosScreen(Screen):
    def __init__(self, **kwargs):
        super(EmprestimosScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.batch_input = TextInput(hint_text="Batch da Ferramenta", multiline=False)
        self.re_input = TextInput(hint_text="RE do Tripulante", multiline=False)
        self.acft_input = TextInput(hint_text="ACFT da Aeronave", multiline=False)
        adicionar_btn = Button(text="Registrar Empréstimo")
        adicionar_btn.bind(on_release=self.registrar_emprestimo)

        layout.add_widget(self.batch_input)
        layout.add_widget(self.re_input)
        layout.add_widget(self.acft_input)
        layout.add_widget(adicionar_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def registrar_emprestimo(self, instance):
        batch = self.batch_input.text
        re = self.re_input.text
        acft = self.acft_input.text
        if batch and re and acft:
            result = registrar_emprestimo(batch, re, acft)
            self.show_popup("Resultado", result)
            self.batch_input.text = ''
            self.re_input.text = ''
            self.acft_input.text = ''
        else:
            self.show_popup("Erro", "Preencha todos os campos.")

    def voltar(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(None, None), size=(600, 150))
        popup.open()


class DevolucoesScreen(Screen):
    def __init__(self, **kwargs):
        super(DevolucoesScreen, self).__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10)

        self.batch_input = TextInput(hint_text="Batch da Ferramenta", multiline=False)
        devolver_btn = Button(text="Devolver Ferramenta")
        devolver_btn.bind(on_release=self.devolver_ferramenta)

        layout.add_widget(self.batch_input)
        layout.add_widget(devolver_btn)

        voltar_btn = Button(text="Voltar", size_hint_y=None, height=50)
        voltar_btn.bind(on_release=self.voltar)
        layout.add_widget(voltar_btn)

        self.add_widget(layout)

    def devolver_ferramenta(self, instance):
        batch = self.batch_input.text
        if batch:
            result = devolver_ferramenta(batch)
            self.show_popup("Resultado", result)
            self.batch_input.text = ''
        else:
            self.show_popup("Erro", "Preencha o campo de Batch.")

    def voltar(self, instance):
        self.manager.current = 'main'

    def show_popup(self, title, message):
        popup = Popup(title=title, content=Label(text=message), size_hint=(None, None), size=(400, 200))
        popup.open()


class GerenciadorApp(App):
    def build(self):
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(TripulantesScreen(name='tripulantes'))
        sm.add_widget(FerramentasScreen(name='ferramentas'))
        sm.add_widget(AeronavesScreen(name='aeronaves'))
        sm.add_widget(HistoricoScreen(name='historico'))
        sm.add_widget(EmprestimosScreen(name='emprestimos'))
        sm.add_widget(DevolucoesScreen(name='devolucoes'))
        return sm


if __name__ == '__main__':
    GerenciadorApp().run()

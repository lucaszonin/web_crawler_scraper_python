#Scrap
import scrapy
from scrapy.exceptions import CloseSpider
import scrapy.crawler as crawler

#Others
import json
import os
import requests
import time
from datetime import date, datetime
from pathlib import Path

#Data Wrangling
import pandas as pd
pd.set_option('display.max_columns', 30)
pd.set_option('display.max_rows', 50)
pd.set_option('expand_frame_repr', False)
from bs4 import BeautifulSoup

#Selenium imports
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
#Executar o crawler só no terminal e não abrir o navegador
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

#Third party
from crawler.spiders.environment import popular

#Só uso para ver os returns
SHOW_DATA = 'extracted.txt'
#Resultado final para inserir no ged depois de todas verificações
JSON_FINAL_FILE = 'jsoned.txt'
#Dados temporários para extrair em formato DataFrame e logo é excluído
DATA_TEMPORARY = 'data_temporary.txt'
#Logs
LOG_FILE = 'log.txt'

class PopularSpider(scrapy.Spider):

    name = 'popularspider'
    start_urls = [popular['site_login']]

    #Pegando a data de hoje
    data_inicial = date.today().strftime("%d/%m/%Y")
    data_final   = date.today().strftime("%d/%m/%Y")

    custom_settings = {'CLOSESPIDER_TIMEOUT' : 120}

    def __init__(self, *a, **kw):
        self.erase_files()  
        self.driver = webdriver.Chrome(popular['chromedriver'], chrome_options=options, service_log_path='/dev/null')
        super().__init__(**kw)
        
        
    #Removing the files below if it exists
    def erase_files(self):        
        if os.path.exists(SHOW_DATA):
            os.remove(SHOW_DATA)
        
        if os.path.exists(JSON_FINAL_FILE):
            os.remove(JSON_FINAL_FILE)

        if os.path.exists(DATA_TEMPORARY):
            os.remove(DATA_TEMPORARY)
   
    #Acessar a página de login e logar
    def parse(self, response):
         
        self.driver.get(popular['site_login'])  

        #Extract all the page
        html_atual = self.driver.page_source

        #Extracting the first table, our data
        soup = BeautifulSoup(html_atual, 'lxml')

        self.loginFarmacia(self.driver)

        return self.parse_crawler_page(self.driver)

    #Acessar a página onde vamos realizar o scraping dos dados        
    def parse_crawler_page(self, driver):

        self.driver.get(popular['site_crawler'])

        self.requestingData(self.driver)
        
        return self.extract_data(self.driver)

    #Aqui ele apenas loopa no etl e troca as páginas
    def extract_data(self, driver):

        #Extracting the total of pages 
        range_pages = driver.find_element_by_xpath('//*[@id="form:tabela_paginator_bottom"]/span[1]').text

        #verifying the total of pages
        if(range_pages[7] != ')'):
            range_pages = int(range_pages[6] + range_pages[7])
        else:
            range_pages = int(range_pages[6])

        #Getting local jquery 
        script_location = Path(__file__).absolute().parent
        file_location = script_location / 'jquery-1.12.4.min.js'        
        jquery = open(str(file_location), "r").read()

        #Somei mais um no range_pages pq ele extrai duas vezes a primeira pagina e entende como 2, mas depois dropo as duplicadas
        contador = 1
        data_frame_inicial = pd.DataFrame()
        while int(range_pages + 1) >= int(contador):

            df = self.extracting_all_pages(self.driver)
            #Inserting the data
            data_frame_inicial = data_frame_inicial.append(df, ignore_index=True)

            #JQuery will change the page
            driver.execute_script(jquery)
            driver.execute_script("""
        
                if (window.jQuery) {  

                    // jQuery is loaded 
                    $(".ui-paginator-next").click();
                    //alert("Página trocada! Número atual:" +  $(".ui-state-active").text());
            
                } else {

                    // jQuery is not loaded
                    alert("Doesn't Work");

                }
                """)
            contador += 1
        
        #Removing duplicated data 
        data_frame_inicial = data_frame_inicial.drop_duplicates()
        self.write_data_temporary(data_frame_inicial)   
        self.etl(self.driver, data_frame_inicial)
        
        print('DADOS INSERIDOS COM SUCESSO!')
        f = open(LOG_FILE, "a+")
        f.write('{} - OK. DADOS INSERIDOS COM ÊXITO\n'.format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
        f.close()
        
    def extracting_all_pages(self, driver):

        #Extract all the page
        content = driver.page_source
        
        #Extracting the first table, our data
        soup  = BeautifulSoup(content, 'lxml')
        table = soup.find_all('table')[0]

        if os.path.exists(DATA_TEMPORARY):
            df = pd.read_html(str(table), thousands = None, skiprows=[0])
        else:
            df = pd.read_html(str(table), thousands = None)
        
        return df[0]
        
    #This function will extract, transform and load all the data found.
    def etl(self, driver, data):

        #VERIFICAR AQUI SE OS DADOS JÁ EXISTEM NO GED
        cupom_validado = self.getCupom(data)

        #Verificar se teve cupons validados
        if cupom_validado.empty:
            print("NÃO HÁ NOVOS DADOS PARA SEREM INSERIDOS!")
            f = open(LOG_FILE, "a+")
            f.write('{} - OK. NÃO HÁ NOVOS DADOS\n'.format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            f.close()
            quit()
  
        #Loopar entre os dados validados.
        for row in cupom_validado.values:
            
           #DADOS QUE VEM DEPOIS DA VALIDAÇÃO
            cupom = row[0]

            #Buscar só as linhas que vão ser cadastradas com base nos dados validados
            filter_data = data.where(data['C. FISCAL'] == cupom)
            filter_data = filter_data.dropna()
            filter_data['AUTORIZAÇÃO'] = filter_data['AUTORIZAÇÃO'].astype(int)
            filter_data['C. FISCAL']   = filter_data['C. FISCAL'].astype(int)
            filter_data['QT. AUTORI.'] = filter_data['QT. AUTORI.'].astype(int)
            filter_data['EAN']         = filter_data['EAN'].astype(int)
 
            if(filter_data['EAN'].count() > 1):

                lista_de_lista = filter_data.to_numpy().tolist()

                #Creating empty list to insert data
                ean_list         = []
                medicamento_list = []
                valor_venda_list = []
                valor_ms_list    = []
                quantidade_list  = []

                #Getting the data
                autorizacao = lista_de_lista[0][0]
                c_fiscal    = lista_de_lista[0][1]
                cpf         = lista_de_lista[0][2]
                timestamp   = lista_de_lista[0][3]
 
                for i in lista_de_lista:
                    
                    #Grouping the data
                    ean_list.append(i[4])
                    medicamento_list.append(i[5])
                    valor_venda_list.append(i[8])
                    valor_ms_list.append(i[7])
                    quantidade_list.append(i[6])
                                    
                data_frame_final = pd.DataFrame({'AUTORIZAÇÃO' : autorizacao,
                                                'C. FISCAL'   : c_fiscal,
                                                'CPF'         : cpf,
                                                'DT.AUT/EST'  : timestamp,
                                                'EAN'         : str(ean_list),
                                                'MEDICAMENTO' : str(medicamento_list),
                                                'QT. AUTORI.' : str(quantidade_list),
                                                'VL.VENDA' : str(valor_venda_list),
                                                'VL.MS.'    : str(valor_ms_list),
                                                },index=[1])

                #transforming to string
                data_frame_final['EAN']          = data_frame_final['EAN'].astype(str)
                data_frame_final['MEDICAMENTO']  = data_frame_final['MEDICAMENTO'].astype(str)
                data_frame_final['VL.VENDA']     = data_frame_final['VL.VENDA'].astype(str)
                data_frame_final['VL.MS.']       = data_frame_final['VL.MS.'].astype(str)
                data_frame_final['QT. AUTORI.']  = data_frame_final['QT. AUTORI.'].astype(str)

            
            else:

                data_frame_final = filter_data

            #Loopar entre os dados filtrados e inserindo no GED
            self.insertData(data_frame_final)  
                          
    #Verificando os dados
    def getCupom(self, data):

        cupom_fiscal_unico = self.separando_por_cupom(data)
 
        #HERE YOU HAVE TO INTEGRATE WITH AN API ---------------------------------------------
        
    #Inserindo no GED
    def insertData(self, dados_inserir):

        #Getting the file created at ETL part.
        for row in dados_inserir.iterrows():
            
            #Preparo os dados para inserir
            autorizacao  = row[1][0]
            cupom_fiscal = row[1][1]
            cpf          = row[1][2]
            data_venda   = row[1][3]
            ean          = row[1][4]
            medicamento  = row[1][5]
            quantidade   = row[1][6]
            valor_venda  = row[1][7]
            valor_ms     = row[1][8]

            #HERE YOU HAVE TO INTEGRATE WITH AN API --------------------------------
                    
    #Separar código de barras por cupom
    def separando_por_cupom(self, data):
        
        #Busco os cupons unicos
        cupom_fiscal_unico = data['C. FISCAL'].unique()

        return cupom_fiscal_unico

    def verifying503(self, driver, html):

        html = str(html)

        html503_1 = "<html><head></head><body></body></html>"

        html503_2 = "<html><head><title>Error</title></head><body>503 - Service Unavailable</body></html>"

        html503_3 = ""

        html503_4 = " "

        if((html503_1 == html) | (html503_2 == html) | (html503_3 == html) | (html503_3 == html)):
            print('ERRO 503')
            f = open(LOG_FILE, "a+")
            f.write('{} - ERRO. 503\n'.format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            f.close()
            quit()

    def write_log_in_file(self, log):
        f = open(LOG_FILE, "a+")
        f.write(str(log))
        f.close()

    def write_result_final(self, json):
        f = open(JSON_FINAL_FILE, "a+")
        f.write(str(json))
        f.close()
    
    def see_output(self, log):
        f = open(SHOW_DATA, "w")
        f.write(str(log))
        f.close()

    def write_data_temporary(self, data):
        f = open('data_temporary.txt', 'a+')
        f.write(str(data))
        f.close()

    #Login function
    def loginFarmacia(self, driver):
    
        #Getting the inputs
        user     = driver.find_element_by_xpath('//*[@id="formLogin:no_login"]')
        password = driver.find_element_by_xpath('//*[@id="formLogin:senha"]')

        #Inserting the data
        user.send_keys(popular['user'])
        password.send_keys(popular['password'])

        #Clicking button
        logar = driver.find_element_by_xpath('//*[@id="formLogin"]/div[1]/fieldset/div[5]/input')
        logar.click()

    #Bring all the data
    def requestingData(self, driver):

        #Selecting inputs
        data_inicio_input = driver.find_element_by_xpath('//*[@id="form:dataInicio_input"]')
        data_final_input  = driver.find_element_by_xpath('//*[@id="form:dataFim_input"]')

        #Inserting the data
        data_inicio_input.send_keys(self.data_inicial)
        data_final_input.send_keys(self.data_final)

        #Clicking the button
        search_button = driver.find_element_by_xpath('//*[@id="form:formulario"]/div/div[8]/input')
        return search_button.click()
 
#5 * * * * <- crontab em produção

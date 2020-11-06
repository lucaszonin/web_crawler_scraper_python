# Web_crawler_Farmacias_Popular
# Selenium , Pandas, Scrapy , BeautifulSoup and Supervisor

Web crawler / scraper para acessar as farmácias popular, logar, inputar as datas, extrair todos os dados, tratar os dados, verificar se já existe o dado na nossa base e se não existe, inserir. 

**Estou usando versão 3.7.3 do Python**
**Estou usando versão 85.0.4183.102 (Versão oficial) 64 bits do Google Chrome**

**Passos para fazer a aplicação rodar:**

**1.:** Após ter clonado este repositório, verifique se você possue virtualenv do Python instalado.

**2.:** Execute virtualenv nome_do_ambiente no terminal **dentro da pasta deste repositório!**

**3.:** Você verá que terá uma nova pasta, este é o ambiente virtual. Inicie o ambiente -> source /nome_do_ambiente/bin/activate

**4.:** Pronto, seu ambiente virtual está ativado. Com este repositório clonado, execute pip -r install requirements.txt

**5.:** Antes de executar a aplicação, altere a PATH do **chromedriver** em /crawler/spiders/enviroment.py. Deixe igual ao **caminho do servidor absoluto**.

**6.:** Dependências do projeto instaladas. Agora podemos executar -> **scrapy crawl popularspider**

**7.:** O comando acima vai executar apenas uma vez o algoritmo e vai encerrar. Para loopar a todo momento, precisamos configurar o Supervisor que já está instalado.

**8.:** Entre na pasta onde você criou seu ambiente virtual e execute -> **echo_supervisord_conf > etc/supervisord.conf**

**9.:** Dentro de **etc/supervisord.conf**, vá até este bloco de código abaixo e deixe da seguinte forma :
```
        [program:popularspider]
        command=scrapy crawl popularspider
        autostart=true
        autorestart=true
        stdout_logfile=/tmp/app.log
        stderr_logfile=/tmp/error.log
```
**Obs: stdout_logfile e stderr_logfile são opcionais!!!**

**10.:** Feito isso, execute **supervisord**. Aplicação iniciada! Veja os logs -> /tmp/app.log ou /tmp/error.log.



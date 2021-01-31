import time
import re
import requests
from bs4 import BeautifulSoup as BS
import psycopg2
from fake_headers import Headers


class Base:     # базовый класс


    def startScraper(self,validateName,validateID,tableName):

        self.validateName = validateName        # имя комплектующего в url
        self.validateID = validateID            # ид комплектующего в url
        self.tableName = tableName              # таблица комплектующего
        self.lineName = []                      # список полей для коммита в БД
        self.productName = []                   # имя комплектующих
        self.price = []                         # цены комплектующих
        self.dnsrate = []                       # рейтинг из днс
        self.productURL = []                    # урлы на комплектующие

        self.session = requests.Session()

        proxylist = {
            #'https' : 'https://mKgQot:pBe45f@213.166.74.36:9373',
            'https' : '192.168.1.108:8888',
            'http':'134.209.29.120:8080'
            #'http': '91.202.240.208:51678'
                      }

        header = Headers(
            browser="chrome",  # Generate only Chrome UA
            os="win",  # Generate ony Windows platform
            headers=False  # generate misc headers
        )

        genHeaders = header.generate()      # генерация заголовков
        genHeaders.update({'Host': 'www.dns-shop.ru'})




        #self.session.headers = genHeaders
        self.session.trust_env = False

        r = self.session.get(
            'https://www.dns-shop.ru/catalog/' + validateID + '/' + validateName + '/?p=1',allow_redirects=False,headers={'User-Agent': 'Chrome/70.0.3538.77'})




        #self.session.headers['Cookie'] = r.headers['Set-Cookie']


        # r = self.session.get(
        #     'https://www.dns-shop.ru/catalog/' + validateID + '/' + validateName + '/?p=1', allow_redirects=False,headers={'User-Agent': 'Chrome/70.0.3538.77','Cookie':r.headers['Set-Cookie']})


        # cookieDict = self.session.cookies.get_dict()
        # cookieResult = ''
        #
        # for k, v in cookieDict.items():
        #     cookieResult += k + '=' + v + '; '



        #self.session.headers['Cookie'] = cookieResult



        #r = self.session.get('https://httpbin.org/response-headers',proxies=proxylist)

        self.html = BS(r.content, 'html.parser')


        self.countPages = int(self.html.select('.pagination-widget__pages > li')[-1]['data-page-number'])  # Количество страниц продуктов

        self.CSRF = self.html.find(attrs={"name": "csrf-token"})['content']



        for j in range(1, self.countPages + 1):  # перебор страниц комплектующих


            r = self.session.get('https://www.dns-shop.ru/catalog/' + validateID + '/' + validateName + '/?p=' + str(j), allow_redirects=False, headers={'User-Agent': 'Chrome/70.0.3538.77'})

            print ('Запрос ',j)

            self.html = BS(r.content, 'html.parser')

            # Парсер названий продуктов
            for el in self.html.select('.product-info__title'):
                result = el.select('.product-info__title-link > a')
                self.productName.append(result[0].text)
                self.productURL.append('https://www.dns-shop.ru'+result[0].get('href'))




            self.getPrice()
            self.getAdditional()
            self.getdnsRate()

            # self.session.headers.clear()    # пересборка хедеров
            # self.session.headers = genHeaders
            # self.session.headers['Cookie'] = cookieResult

        self.makeSQL()


    def makeSQL(self):



        self.conn = psycopg2.connect(dbname='postgres', user='postgres',
                                password='29886622ss', host='localhost')
        self.cursor = self.conn.cursor()

        self.cursor.execute("set schema 'scraper'; truncate {0} RESTART IDENTITY".format(
            self.tableName))

        self.cursor.execute(
            "select column_name from information_schema.columns where table_name = '{}' and table_schema = 'scraper';".format(self.tableName))  # получение столбцов таблицы

        rowName = []

        for i in self.cursor.fetchall():  # формирование списка столбцов    последнюю колонку не считаем, т.к там rating
            if (i[0]!='benchrating'):          # собираем имена колонок кроме benchrating, т.к она есть не во всех таблицах
                rowName.append(i[0])


        d = {}  # dict словарь
        for i in range(len(self.productName)):
            for j in range(1, len(rowName)):
                d.update({rowName[j]: self.lineName[j - 1][i]})


            sql = "set schema 'scraper'; INSERT INTO {tablename} ({columns}) VALUES {values};".format(  # Инсёртим данные
                tablename=self.tableName,
                columns=', '.join(d.keys()),
                values=tuple(d.values())
            )
            self.cursor.execute(sql)

        self.conn.commit()


    def getPrice(self):  # функция формирования цен



        priceID = []
        productID = []



        for i in self.html.select('.n-catalog-product__price > span'):
            priceID.append(i['id'])

        for i in self.html.select('.catalog-item'):
            productID.append(i['data-guid'])

        datatest = 'data={"type":"min-price","containers":['

        for i in range(len(priceID)):

            if (i == len(priceID) - 1):
                datatest += '{"id":"' + str(priceID[i]) + '","data":{"id":"' + str(
                    productID[i]) + '"}}'
            else:
                datatest += '{"id":"' + str(priceID[i]) + '","data":{"id":"' + str(
                    productID[i]) + '"}},'

        datatest += ']}'



        # self.session.headers['X-Requested-With'] = 'XMLHttpRequest'
        # self.session.headers['content-type'] = 'application/x-www-form-urlencoded'
        # self.session.headers['X-CSRF-Token'] = self.CSRF
        # self.session.headers['Referer'] = 'https://www.dns-shop.ru/catalog/17a899cd16404e77/processory/no-referrer'
        # self.session.headers['Content-Length'] = str(len(datatest))
        r = self.session.post('https://www.dns-shop.ru/ajax-state/min-price/?cityId=128',headers={'User-Agent': 'Chrome/70.0.3538.77',
                                                                                   'X-Requested-With': 'XMLHttpRequest',
                                                                                   'content-type': 'application/x-www-form-urlencoded',
                                                                                   'X-CSRF-Token': self.CSRF}, data=datatest)




        for i in range(len(priceID)):
            self.price.append(r.json()['data']['states'][i]['data']['current'])



    def getAdditional(self):
        pass

    def getbenchRating(self):      # метод для парсинга рейтинга комплектующих

        rate = []

        r = self.session.get(
            'https://www.'+self.urlrate+'',
            headers={'User-Agent': 'Chrome/86.0.4240.75'})

        html = BS(r.content, 'html.parser')

        for i in html.select('#cputable > tbody > tr'):
            name = i.select('td:nth-child(1) > a')[0].text
            rating = i.select('td:nth-child(2)')[0].text
            rating = rating.replace(',', '')
            rate.append([name, rating])

        for i in range(len(self.productName)):
            for j in range(len(rate)):
                if ('@' in rate[j][0]):     # если есть символа @ в имени продукта
                    match = re.search(r'(.*?)@', rate[j][0])
                    match = match.groups()[0][:-1]      # избавляемся от символа @

                    if (re.search(r'\b' + match.upper() + r'\b', self.productName[i].upper()) != None):     # ищем обработанное имя из списка бенчмарка в списке ДНСа
                        self.cursor.execute(
                            "update scraper.{tablename} set benchrating ={rating} where name='{name}';".format(     # апдейтим столбик бенчмарка
                                name=self.productName[i], rating=rate[j][1],tablename=self.tableName))




                else:   # аналогично выше, только в имени комплектующего в списке бенчмарка не было символа @
                    if (re.search(r'\b' + rate[j][0].upper() + r'\b', self.productName[i].upper()) != None):
                        self.cursor.execute(
                            "update scraper.{tablename} set benchrating ={rating} where name='{name}';".format(
                                name=self.productName[i], rating=rate[j][1],tablename=self.tableName))




        self.conn.commit()



    def getdnsRate(self):



        rating = []

        for element in self.html.find_all(
                attrs={"class": "product-info__rating"}):  # рейтинг по каждому элементу страницы
            rating.append(float(element['data-rating']))

        for index, el in enumerate(self.html.select('.product-info')):
            try:
                dnsrate = el.select('.product-info__stat > a.product-info__opinions-count')         # количество оценок
                dnsrate = int(dnsrate[0].text)
                dnsrate = dnsrate * rating[index]     # умножение количества оценок на рейтинг
            except:
                dnsrate = 0


            self.dnsrate.append(round(dnsrate))



class CPU(Base):
    def __init__(self, validateName, validateID, tableName,urlrate):

        self.SocketName = []  # имя сокета
        self.PowerName = []  # герцовка
        self.CountCPUs = []  # количество ядер
        self.TDP = []       # TDP процессора
        self.urlrate = urlrate  # ссылка на сайт с рейтингом


        self.startScraper(validateName,validateID,tableName)

    def getAdditional(self):


        self.lineName.extend([self.productName, self.SocketName, self.PowerName, self.CountCPUs,self.TDP, self.price, self.dnsrate, self.productURL])  # объединение списков в один список для коммита последующего



        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchSocket = re.search(r'\[(.*?)\,', result)
            matchPower = re.search(r'x(.*?)М', result)
            matchCountCpus = re.search(r', \d{1,2}', result)
            matchTDP = re.search(r'\d{2,3} Вт',result)


            self.SocketName.append(matchSocket.group()[1:-1])
            self.PowerName.append(matchPower.group()[2:-2])
            self.CountCPUs.append(matchCountCpus.group()[2:])
            self.TDP.append(matchTDP.group()[:-2])


class Mother(Base):
    def __init__(self, validateName, validateID, tableName):
        self.SocketName = []  # имя сокета
        self.CountSlotRam = []  # количество слотов
        self.RamName = []  # имя слота ОЗУ
        self.PowerRam = []  # мгц слота ОЗУ
        self.Chipset = [] # чипсет

        self.startScraper(validateName,validateID,tableName)

    def getAdditional(self):

        self.lineName = [self.productName, self.SocketName, self.CountSlotRam, self.RamName, self.PowerRam, self.price, self.Chipset,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу

        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchSocket = re.search(r'\[(.*?)\,', result)
            matchSlot = re.search(r' \d{1}x', result)
            matchRam = re.search(r'xDDR\d{0,1}', result)
            matchPowerRam = re.search(r'\d{3,4} М', result)


            self.Chipset.append(result.split(',')[1][1:])   # наименование чипсета
            self.SocketName.append(matchSocket.group()[1:-1])
            self.CountSlotRam.append(matchSlot.group()[1:-1])
            self.RamName.append(matchRam.group()[1:])
            self.PowerRam.append(matchPowerRam.group()[:-2])

class Video(Base):
    def __init__(self, validateName, validateID, tableName,urlrate):
        self.SocketName = []  # Имя разъёма
        self.PowerName = []  # герцовка
        self.VideoRAM = []  # Память видеокарты
        self.VideoBus = []  # шина видеокарты
        self.VideoBlockRec = [] # рекомендуемая мощность блока питания
        self.urlrate = urlrate # ссылка на сайт с рейтингом


        self.startScraper(validateName,validateID,tableName)

    def getAdditional(self):
        self.lineName = [self.productName, self.SocketName, self.PowerName, self.VideoRAM, self.VideoBus, self.VideoBlockRec, self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу


        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchSocket = re.search(r'\[(.*?)\,', result)
            matchPower = re.search(r'\d{3,4} М', result)
            matchRAM = re.search(r', \d{1,2} Г', result)
            matchBus = re.search(r'\d{2,3} б', result)

            self.SocketName.append(matchSocket.group()[1:-1])
            self.PowerName.append(matchPower.group()[:-2])
            self.VideoRAM.append(matchRAM.group()[2:-2])
            self.VideoBus.append(matchBus.group()[:-2])

        for el in self.html.select('.product-info__title-link > a'):        # запросы для сборки мощности рекомендуемого блока питания
            detailUrl = el.get('href')     # парсинг по имени

            r = self.session.get('https://www.dns-shop.ru'+detailUrl+'characteristics/',
                                 allow_redirects=False, headers={'User-Agent': 'Chrome/70.0.3538.77'})


            self.detailVideo = BS(r.content, 'html.parser')

            self.VideoBlockRec.append(self.detailVideo.select_one('tr:contains(" Рекомендуемый блок питания ")').text.split()[3])         # парсинг рекомендуемой мощности блока питания для каждой видеокарты на странице





class RAM(Base):
    def __init__(self, validateName, validateID, tableName):
        self.SocketName = []  # имя сокета
        self.PowerName = []  # герцовка
        self.CountRAMs = []  # количество ядер
        self.MemorySize = []  # количество гигабайт

        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):
        self.lineName = [self.productName, self.SocketName, self.PowerName, self.CountRAMs, self.MemorySize,self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу

        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchSocket = re.search(r'\[(.*?)\,', result)
            matchPower = re.search(r'\d{3,4} М', result)
            matchCount = re.search(r'\d{1,2} шт', result)
            matchSize = re.search(r'\d{1,2} ГБ', result)

            self.SocketName.append(matchSocket.group()[1:-1])
            self.PowerName.append(matchPower.group()[:-2])
            self.CountRAMs.append(matchCount.group()[:-3])
            self.MemorySize.append(matchSize.group()[:-3])

class Block(Base):
    def __init__(self, validateName, validateID, tableName):
        self.PowerBlock = []

        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):


        self.lineName = [self.productName, self.PowerBlock, self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchPower = re.search(r'\d{3,4} Вт', result)

            self.PowerBlock.append(matchPower.group()[:-3])

class SSD(Base):
    def __init__(self, validateName, validateID, tableName):
        self.WriteSSD = []  # имя сокета
        self.ReadSSD = []  # герцовка
        self.SizeSSD = [] # размер ССД диска
        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):


        self.lineName = [self.productName, self.SizeSSD, self.WriteSSD,self.ReadSSD, self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')           # парсинг доп. информации
            result = result[0].text



            try:
                matchWrite = re.search(r'запись - \d{3,4}', result)
                self.WriteSSD.append(matchWrite.group()[9:])

            except:
                matchWrite = 0
                self.WriteSSD.append(matchWrite)

            try:
                matchRead = re.search(r'чтение - \d{3,4}', result)
                self.ReadSSD.append(matchRead.group()[9:])
            except:
                matchRead = 0
                self.ReadSSD.append(matchRead)

        for el in self.html.select('.product-info__title'):
            result = el.select('.product-info__title-link > a')     # парсинг по имени
            result = result[0].text

            matchSize = re.search(r'\d{1,4} ', result)              # сохранение размера SSD
            self.SizeSSD.append(matchSize.group()[:-1])


class HDD(Base):
    def __init__(self, validateName, validateID, tableName):
        self.Size = []  # имя сокета

        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):


        self.lineName = [self.productName, self.Size,self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info__title'):
            result = el.select('.product-info__title-link > a')
            result = result[0].text

            matchSize = re.search(r'\d{1,3} ', result)
            if (len(matchSize.group()[:-1]) > 2):  # если указаны Гб то просто записываем
                self.Size.append(matchSize.group()[:-1])
            else:
                self.Size.append(int(matchSize.group()[:-1]) * 1000)  # если указаны ТБ то переводим в ГБ

class Cooler(Base):
    def __init__(self, validateName, validateID, tableName):
        self.Watt = []  # имя сокета


        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):


        self.lineName = [self.productName, self.Watt,self.price,
                         self.dnsrate, self.productURL]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text

            try:
                matchWatt = re.search(r'\d{2,3} В', result)
                self.Watt.append(matchWatt.group()[:-2])
            except:
                matchWatt = 0
                self.Watt.append(matchWatt)


class resultBuild:


    def getBuilds(self):
        conn = psycopg2.connect(dbname='postgres', user='postgres', password='29886622ss', host='localhost')
        cursor = conn.cursor()

        cursor.execute("set schema 'scraper'; select * from cpu;")

        self.cpu_id = []
        self.cpu_name = []
        self.cpu_socket = []
        self.cpu_price = []
        self.cpu_bench = []
        self.cpu_dnsrate = []
        self.cpu_tdp = []

        for i in cursor.fetchall():
            self.cpu_id.append(i[0])
            self.cpu_name.append(i[1])
            self.cpu_socket.append(i[2])
            self.cpu_tdp.append(i[5])
            self.cpu_price.append(i[6])
            self.cpu_dnsrate.append(i[7])
            self.cpu_bench.append(i[8])

        cursor.execute("set schema 'scraper'; select * from video;")

        self.video_id = []
        self.video_name = []
        self.video_socket = []
        self.video_price = []
        self.video_bench = []
        self.video_dnsrate = []
        self.video_blockwatt = []

        for i in cursor.fetchall():
            self.video_id.append(i[0])
            self.video_name.append(i[1])
            self.video_socket.append(i[2])
            self.video_blockwatt.append(i[6])
            self.video_price.append(i[7])
            self.video_dnsrate.append(i[8])
            self.video_bench.append(i[9])

        cursor.execute("set schema 'scraper'; select * from mother;")

        self.mother_id = []
        self.mother_name = []
        self.mother_socket = []
        self.mother_slotsram = []
        self.mother_ramname = []
        self.mother_price = []
        self.mother_chipset = []
        self.mother_dnsrate = []
        self.mother_rampower = []

        for i in cursor.fetchall():
            self.mother_id.append(i[0])
            self.mother_name.append(i[1])
            self.mother_socket.append(i[2])
            self.mother_slotsram.append(i[3])
            self.mother_ramname.append(i[4])
            self.mother_rampower.append(i[5])
            self.mother_price.append(i[6])
            self.mother_chipset.append(i[7])
            self.mother_dnsrate.append(i[8])

        cursor.execute("set schema 'scraper'; select * from ram;")

        self.ram_id = []
        self.ram_name = []
        self.ram_socket = []
        self.ram_count = []
        self.ram_memory = []
        self.ram_price = []
        self.ram_dnsrating = []
        self.ram_power = []

        for i in cursor.fetchall():
            self.ram_id.append(i[0])
            self.ram_name.append(i[1])
            self.ram_socket.append(i[2])
            self.ram_power.append(i[3])
            self.ram_count.append(i[4])
            self.ram_memory.append(i[5])
            self.ram_price.append(i[6])
            self.ram_dnsrating.append(i[7])

        cursor.execute("set schema 'scraper'; select * from block;")

        self.block_id = []
        self.block_name = []
        self.block_price = []
        self.block_dnsrating = []
        self.block_power = []

        for i in cursor.fetchall():
            self.block_id.append(i[0])
            self.block_name.append(i[1])
            self.block_power.append(i[2])
            self.block_price.append(i[3])
            self.block_dnsrating.append(i[4])

        cursor.execute("set schema 'scraper'; select * from ssd;")

        self.ssd_id = []
        self.ssd_name = []
        self.ssd_price = []
        self.ssd_dnsrating = []
        self.ssd_size = []

        for i in cursor.fetchall():
            self.ssd_id.append(i[0])
            self.ssd_name.append(i[1])
            self.ssd_size.append(i[2])
            self.ssd_price.append(i[5])
            self.ssd_dnsrating.append(i[6])

        cursor.execute("set schema 'scraper'; select * from hdd;")

        self.hdd_id = []
        self.hdd_name = []
        self.hdd_size = []
        self.hdd_price = []
        self.hdd_dnsrating = []

        for i in cursor.fetchall():
            self.hdd_id.append(i[0])
            self.hdd_name.append(i[1])
            self.hdd_size.append(i[2])
            self.hdd_price.append(i[3])
            self.hdd_dnsrating.append(i[4])

        cursor.execute("set schema 'scraper'; select * from cooler;")

        self.cooler_id = []
        self.cooler_name = []
        self.cooler_watt = []
        self.cooler_price = []
        self.cooler_dnsrating = []

        for i in cursor.fetchall():
            self.cooler_id.append(i[0])
            self.cooler_name.append(i[1])
            self.cooler_watt.append(i[2])
            self.cooler_price.append(i[3])
            self.cooler_dnsrating.append(i[4])


        self.getGameBuild()
        #self.getOfficeBuild()


    def getGameBuild(self):
        ###################### Паттерны (настройки) для сборок####################

        tdpIndex = 0.7  # индекс на который tdp кулера должен превышать процессорный, по формуле tdp+tdp*0.5
        ramType = 'DDR4'  # тип актуальной оперативной памяти
        recCountRAM = 8  # рекомендуемый размер оперативной памяти для одной планки по умолчанию
        recCountHDD = 1000  # рекомаендуемый размер HDD по умолчанию
        recCountSSD = 120  # рекомаендуемый размер SSD по умолчанию
        needFindVideo = True  # флаг для поиска видеокарт в других ценовых категориях ввиду отсутствия их на рынке.
        companyCPU = [' ', 'AMD', 'Intel']
        companyVideo = [' ', 'GeForce', 'Radeon']

        resultBuild = []  # массив для окончательной сборки
        generateBuild = []  # массив для генерируемых сборок
        idResultBuild = []  # идентификаторы окончательной сборки
        comboIndex = 1  # индекс для комбинации сборок
        stopBuild = False  # аварийное завершение сборщика, в случае если не удаётся найти комплектующие (как правило связано с кризисом видеокарт)

        for comboCPUindex in companyCPU:
            for comboVideoindex in companyVideo:
                stopBuild = False
                for generalprice in range(30000, 150000, 1000):

                    if generalprice <= 40000:
                        maxCpuProc = 0.23
                        maxVideoPrice = 0.24
                        maxRamPrice = 0.13
                        maxMotherPrice = 0.18
                        maxHddPrice = 0.1
                        maxSSDPrice = 0  # не нужен
                        maxBlockPrice = 0.09
                        maxcoolerprice = 0.03

                        recCountRAM = 4
                        recCountHDD = 1000


                    elif generalprice > 40000 and generalprice <= 50000:
                        maxCpuProc = 0.21
                        maxVideoPrice = 0.32
                        maxRamPrice = 0.12
                        maxMotherPrice = 0.13
                        maxHddPrice = 0.08
                        maxSSDPrice = 0.05
                        maxBlockPrice = 0.07
                        maxcoolerprice = 0.02

                        recCountHDD = 1000
                        recCountRAM = 8
                        recCountSSD = 120

                    elif generalprice > 50000 and generalprice <= 60000:
                        maxCpuProc = 0.24
                        maxVideoPrice = 0.34
                        maxRamPrice = 0.1
                        maxMotherPrice = 0.11
                        maxHddPrice = 0.06
                        maxSSDPrice = 0.05
                        maxBlockPrice = 0.08
                        maxcoolerprice = 0.02

                        recCountHDD = 1000
                        recCountRAM = 8
                        recCountSSD = 240

                    elif generalprice > 60000 and generalprice <= 70000:
                        maxCpuProc = 0.23
                        maxVideoPrice = 0.36
                        maxRamPrice = 0.09
                        maxMotherPrice = 0.12
                        maxHddPrice = 0.05
                        maxSSDPrice = 0.04
                        maxBlockPrice = 0.09
                        maxcoolerprice = 0.02

                        recCountHDD = 1000
                        recCountSSD = 240
                        recCountRAM = 8

                    elif generalprice > 70000 and generalprice <= 100000:
                        maxCpuProc = 0.21
                        maxVideoPrice = 0.35
                        maxRamPrice = 0.11
                        maxMotherPrice = 0.1
                        maxHddPrice = 0.05
                        maxSSDPrice = 0.07
                        maxBlockPrice = 0.08
                        maxcoolerprice = 0.03

                        recCountHDD = 1000
                        recCountSSD = 480
                        recCountRAM = 8
                    elif generalprice > 100000 and generalprice <= 150000:
                        maxCpuProc = 0.22
                        maxVideoPrice = 0.36
                        maxRamPrice = 0.1
                        maxMotherPrice = 0.1
                        maxHddPrice = 0.035
                        maxSSDPrice = 0.085
                        maxBlockPrice = 0.06
                        maxcoolerprice = 0.04

                        recCountHDD = 2000
                        recCountRAM = 16
                        recCountSSD = 960

                    else:  # больше 150к  # свободных 2 процента
                        maxCpuProc = 0.2
                        maxVideoPrice = 0.40
                        maxRamPrice = 0.07
                        maxMotherPrice = 0.11
                        maxHddPrice = 0.04
                        maxSSDPrice = 0.07
                        maxBlockPrice = 0.06
                        maxcoolerprice = 0.05

                        recCountHDD = 2000
                        recCountRAM = 16
                        recCountSSD = 960

                    maxCpuPrice = generalprice * maxCpuProc
                    maxVideoPrice *= generalprice
                    maxRamPrice *= generalprice
                    maxMotherPrice *= generalprice
                    maxHddPrice *= generalprice
                    maxSSDPrice *= generalprice
                    maxBlockPrice *= generalprice
                    maxcoolerprice *= generalprice

                    minCpuPrice = maxCpuPrice * 0.7
                    minVideoPrice = maxVideoPrice * 0.9
                    minRamPrice = maxRamPrice * 0.65
                    minMotherPrice = maxMotherPrice * 0.7
                    minHddPrice = maxHddPrice * 0.7
                    minSSDPrice = maxSSDPrice * 0.5
                    minBlockPrice = maxBlockPrice * 0.8
                    mincoolerprice = maxcoolerprice * 0.6

                    k = 0
                    resultprice = 0  # результирующая стоимость сборки

                    while resultprice / generalprice < 0.9:

                        resultprice = 0

                        generateBuild.clear()

                        ############### Поиск ЦПУ
                        max = 0  # для поиска максимального по benchrating комплектующего (далее аналогично)
                        cpuIndex = 0

                        for i in range(len(self.cpu_name)):

                            if (self.cpu_bench[i] != None and self.cpu_bench[i] > max and 'OEM' in self.cpu_name[i] and comboCPUindex in
                            self.cpu_name[i] and self.cpu_price[i] <= maxCpuPrice and self.cpu_price[i] >= minCpuPrice):
                                max = self.cpu_bench[i]
                                cpuIndex = i

                        maxCpuPrice += 50

                        generateBuild.append(
                            [self.cpu_name[cpuIndex], self.cpu_tdp[cpuIndex], self.cpu_socket[cpuIndex], self.cpu_price[cpuIndex]])
                        resultprice += self.cpu_price[cpuIndex]

                        ################### Поиск Видеокарты
                        max = 0
                        videoIndex = 0

                        if needFindVideo == True:  # если ситуация с видеокартами кризисная
                            while videoIndex == 0:

                                for i in range(len(self.video_name)):

                                    if (self.video_bench[i] != None and self.video_bench[i] > max and self.video_price[
                                        i] <= maxVideoPrice and comboVideoindex in self.video_name[i] and self.video_price[
                                        i] > minVideoPrice):
                                        max = self.video_bench[i]
                                        videoIndex = i

                                minVideoPrice -= 50

                                if minVideoPrice < 0:
                                    break
                        else:
                            for i in range(len(self.video_name)):

                                if (self.video_bench[i] != None and self.video_bench[i] > max and self.video_price[
                                    i] <= maxVideoPrice and comboVideoindex in self.video_name[i] and self.video_price[
                                    i] > minVideoPrice):
                                    max = self.video_bench[i]
                                    videoIndex = i

                        maxVideoPrice += 50

                        generateBuild[k].extend((self.video_name[videoIndex], self.video_price[videoIndex]))
                        resultprice += self.video_price[videoIndex]

                        ################### Поиск Материнки
                        max = 0
                        motherIndex = 0

                        for i in range(len(self.mother_name)):
                            if (self.cpu_socket[cpuIndex] == self.mother_socket[i] and self.mother_ramname[i] == ramType and
                                    self.mother_dnsrate[i] > max and self.mother_price[i] <= maxMotherPrice and self.mother_price[
                                        i] >= minMotherPrice):
                                max = self.mother_dnsrate[i]
                                motherIndex = i

                        generateBuild[k].extend((self.mother_name[motherIndex], self.mother_ramname[motherIndex],
                                                 self.mother_rampower[motherIndex], self.mother_price[motherIndex]))
                        resultprice += self.mother_price[motherIndex]

                        maxMotherPrice += 50
                        #################### Поиск ОЗУ
                        max = 0
                        ramIndex = 0

                        for i in range(len(self.ram_name)):
                            if self.ram_socket[i] == self.mother_ramname[motherIndex] and self.ram_dnsrating[i] > max and self.ram_price[
                                i] >= minRamPrice and (
                                    (self.ram_count[i] >= 2 and self.ram_memory[i] == recCountRAM and self.ram_price[
                                        i] <= maxRamPrice) or (
                                            self.ram_count[i] == 1 and self.ram_memory[i] == recCountRAM and self.ram_price[
                                        i] * 2 <= maxRamPrice)):
                                max = self.ram_dnsrating[i]
                                ramIndex = i

                        if self.ram_count[
                            ramIndex] == 1:  # если в комплекте 1 планка, то удваиваем цену и количество т.к берём по две.
                            generateBuild[k].extend(
                                (self.ram_name[ramIndex], self.ram_count[ramIndex] * 2, self.ram_price[ramIndex] * 2))
                            resultprice += self.ram_price[ramIndex]
                        else:
                            generateBuild[k].extend((self.ram_name[ramIndex], self.ram_count[ramIndex], self.ram_price[ramIndex]))
                            resultprice += self.ram_price[ramIndex]

                        maxRamPrice += 50

                        ###################### Поиск HDD
                        max = 0
                        hddIndex = 0

                        for i in range(len(self.hdd_name)):

                            if (self.hdd_dnsrating[i] > max and self.hdd_price[i] <= maxHddPrice and self.hdd_size[i] == recCountHDD and
                                    self.hdd_price[i] >= minHddPrice):
                                max = self.hdd_dnsrating[i]
                                hddIndex = i

                        generateBuild[k].extend((self.hdd_name[hddIndex], self.hdd_size[hddIndex], self.hdd_price[hddIndex]))
                        resultprice += self.hdd_price[hddIndex]

                        maxHddPrice += 50

                        ###################### Поиск SSD
                        max = 0
                        ssdIndex = 0

                        for i in range(len(self.ssd_name)):
                            if (self.ssd_dnsrating[i] > max and self.ssd_size[i] >= recCountSSD and self.ssd_size[
                                i] <= recCountSSD + 60 and self.ssd_price[i] <= maxSSDPrice and self.ssd_price[i] >= minSSDPrice):
                                max = self.ssd_dnsrating[i]
                                ssdIndex = i

                        if maxSSDPrice != 0:
                            generateBuild[k].extend((self.ssd_name[ssdIndex], self.ssd_price[ssdIndex]))
                            resultprice += self.ssd_price[ssdIndex]

                            maxSSDPrice += 50
                        ####################### Поиск БП

                        max = 0
                        blockIndex = 0

                        for i in range(len(self.block_name)):
                            if (self.block_dnsrating[i] > max and self.block_power[i] >= self.video_blockwatt[videoIndex] and
                                    self.block_power[
                                        i] <= self.video_blockwatt[videoIndex] + 100 and self.block_price[i] <= maxBlockPrice and
                                    self.block_price[
                                        i] >= minBlockPrice):
                                max = self.block_dnsrating[i]
                                blockIndex = i

                        generateBuild[k].extend(
                            (self.block_name[blockIndex], self.block_power[blockIndex], self.block_price[blockIndex]))
                        resultprice += self.block_price[blockIndex]

                        maxBlockPrice += 50
                        ######################## Поиск кулера

                        max = 0
                        coolerIndex = 0

                        for i in range(len(self.cooler_name)):
                            if (self.cooler_dnsrating[i] > max and self.cooler_watt[i] >= self.cpu_tdp[cpuIndex] + self.cpu_tdp[
                                cpuIndex] * tdpIndex and self.cooler_price[i] <= maxcoolerprice and self.cooler_price[
                                i] >= mincoolerprice):  # учет TDP, рейтинга ДНС и диапозона цен
                                max = self.cooler_dnsrating[i]
                                coolerIndex = i

                        generateBuild[k].extend(
                            (self.cooler_name[coolerIndex], self.cooler_watt[coolerIndex], self.cooler_price[coolerIndex]))
                        resultprice += self.cooler_price[coolerIndex]

                        maxcoolerprice += 50

                        if maxVideoPrice * 0.7 > generalprice:  # если цена на любое комплектующее (н-р видеокарта) начинает превышать искомую цену, значит уходим в бесконечность и завершаем работу в текущей итерации.
                            stopBuild = True
                            break

                    if stopBuild == True:  # завершаем работу по поиску комплектующих для текущей комбинации
                        break

                    k += 1

                    resultBuild.extend(generateBuild)

                    if (maxSSDPrice!=0):
                        idResultBuild.append(
                            [self.cpu_id[cpuIndex], self.video_id[videoIndex], self.mother_id[motherIndex], self.ram_id[ramIndex],self.hdd_id[hddIndex],
                             self.ssd_id[ssdIndex], self.block_id[blockIndex], self.cooler_id[coolerIndex], comboIndex, resultprice])
                    else:
                        idResultBuild.append(
                            [self.cpu_id[cpuIndex], self.video_id[videoIndex], self.mother_id[motherIndex],
                             self.ram_id[ramIndex], self.hdd_id[hddIndex],0,self.block_id[blockIndex], self.cooler_id[coolerIndex], comboIndex,
                             resultprice])
                    print('Индекс', comboIndex, 'Стоимость', resultprice, 'Целевая', generalprice, 'Сборка',generateBuild)

                comboIndex += 1

        self.makeSql(idResultBuild)

    def getOfficeBuild(self):
        return

    def makeSql(self,idResultBuild):
        conn = psycopg2.connect(dbname='postgres', user='postgres',
                                password='29886622ss', host='localhost')
        cursor = conn.cursor()

        cursor.execute("set schema 'scraper'; truncate allbuilds RESTART IDENTITY")

        rowName = []
        cursor.execute(
            "select column_name from information_schema.columns where table_name = 'allbuilds' and table_schema = 'scraper';")

        for i in cursor.fetchall():  # формирование списка столбцов    последнюю колонку не считаем, т.к там rating
            if i[0] != 'id':
                rowName.append(i[0])

        d = {}  # dict словарь
        for i in range(len(idResultBuild)):
            for j in range(len(rowName)):
                    d.update({rowName[j]: idResultBuild[i][j]})

            sql = "set schema 'scraper'; insert into allBuilds ({columns}) VALUES {values};".format(
                # Инсёртим данные
                columns=', '.join(d.keys()),
                values=tuple(d.values())
            )

            cursor.execute(sql)

        conn.commit()

if __name__ == "__main__":

    resultBuild().getBuilds()



    # CPU = CPU("processory", "17a899cd16404e77","cpu","cpubenchmark.net/cpu_list.php#single-cpu")
    # CPU.getbenchRating()
    # Video = Video("videokarty", "17a89aab16404e77","video","videocardbenchmark.net/gpu_list.php")
    # Video.getbenchRating()
    # RAM = RAM("operativnaya-pamyat-dimm", "17a89a3916404e77","ram")
    # Mother = Mother("materinskie-platy", "17a89a0416404e77","mother")
    # Block = Block("bloki-pitaniya", "17a89c2216404e77","block")
    # SSD = SSD("ssd-nakopiteli", "8a9ddfba20724e77","ssd")
    # HDD = HDD("zhestkie-diski-35", "17a8914916404e77","hdd")
    # Cooler = Cooler("kulery-dlya-processorov", "17a9cc2d16404e77","cooler")

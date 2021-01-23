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


        self.lineName.extend([self.productName, self.SocketName, self.PowerName, self.CountCPUs,self.TDP, self.price, self.dnsrate])  # объединение списков в один список для коммита последующего



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
                         self.dnsrate]  # список строк для коммита в таблицу

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
                         self.dnsrate]  # список строк для коммита в таблицу


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
                         self.dnsrate]  # список строк для коммита в таблицу

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
                         self.dnsrate]  # список строк для коммита в таблицу
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
                         self.dnsrate]  # список строк для коммита в таблицу
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
                         self.dnsrate]  # список строк для коммита в таблицу
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
                         self.dnsrate]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text

            try:
                matchWatt = re.search(r'\d{2,3} В', result)
                self.Watt.append(matchWatt.group()[:-2])
            except:
                matchWatt = 0
                self.Watt.append(matchWatt)



def getBuilds():
    conn = psycopg2.connect(dbname='postgres', user='postgres', password='29886622ss', host='localhost')
    cursor = conn.cursor()

    cursor.execute("set schema 'scraper'; select * from cpu;")

    cpu_id = []
    cpu_name = []
    cpu_socket = []
    cpu_price = []
    cpu_bench = []
    cpu_dnsrate = []
    cpu_tdp = []

    for i in cursor.fetchall():
        cpu_id.append(i[0])
        cpu_name.append(i[1])
        cpu_socket.append(i[2])
        cpu_tdp.append(i[5])
        cpu_price.append(i[6])
        cpu_dnsrate.append(i[7])
        cpu_bench.append(i[8])

    cursor.execute("set schema 'scraper'; select * from video;")

    video_id = []
    video_name = []
    video_socket = []
    video_price = []
    video_bench = []
    video_dnsrate = []
    video_blockwatt = []

    for i in cursor.fetchall():
        video_id.append(i[0])
        video_name.append(i[1])
        video_socket.append(i[2])
        video_blockwatt.append(i[6])
        video_price.append(i[7])
        video_dnsrate.append(i[8])
        video_bench.append(i[9])

    cursor.execute("set schema 'scraper'; select * from mother;")

    mother_id = []
    mother_name = []
    mother_socket = []
    mother_slotsram = []
    mother_ramname = []
    mother_price = []
    mother_chipset = []
    mother_dnsrate = []
    mother_rampower = []

    for i in cursor.fetchall():
        mother_id.append(i[0])
        mother_name.append(i[1])
        mother_socket.append(i[2])
        mother_slotsram.append(i[3])
        mother_ramname.append(i[4])
        mother_rampower.append(i[5])
        mother_price.append(i[6])
        mother_chipset.append(i[7])
        mother_dnsrate.append(i[8])

    cursor.execute("set schema 'scraper'; select * from ram;")

    ram_id = []
    ram_name = []
    ram_socket = []
    ram_count = []
    ram_memory = []
    ram_price = []
    ram_dnsrating = []
    ram_power = []

    for i in cursor.fetchall():
        ram_id.append(i[0])
        ram_name.append(i[1])
        ram_socket.append(i[2])
        ram_power.append(i[3])
        ram_count.append(i[4])
        ram_memory.append(i[5])
        ram_price.append(i[6])
        ram_dnsrating.append(i[7])

    cursor.execute("set schema 'scraper'; select * from block;")

    block_id = []
    block_name = []
    block_price = []
    block_dnsrating = []
    block_power = []

    for i in cursor.fetchall():
        block_id.append(i[0])
        block_name.append(i[1])
        block_power.append(i[2])
        block_price.append(i[3])
        block_dnsrating.append(i[4])

    cursor.execute("set schema 'scraper'; select * from ssd;")

    ssd_id = []
    ssd_name = []
    ssd_price = []
    ssd_dnsrating = []
    ssd_size = []

    for i in cursor.fetchall():
        ssd_id.append(i[0])
        ssd_name.append(i[1])
        ssd_size.append(i[2])
        ssd_price.append(i[5])
        ssd_dnsrating.append(i[6])

    cursor.execute("set schema 'scraper'; select * from hdd;")

    hdd_id = []
    hdd_name = []
    hdd_size = []
    hdd_price = []
    hdd_dnsrating = []

    for i in cursor.fetchall():
        hdd_id.append(i[0])
        hdd_name.append(i[1])
        hdd_size.append(i[2])
        hdd_price.append(i[3])
        hdd_dnsrating.append(i[4])

    cursor.execute("set schema 'scraper'; select * from cooler;")

    cooler_id = []
    cooler_name = []
    cooler_watt = []
    cooler_price = []
    cooler_dnsrating = []

    for i in cursor.fetchall():
        cooler_id.append(i[0])
        cooler_name.append(i[1])
        cooler_watt.append(i[2])
        cooler_price.append(i[3])
        cooler_dnsrating.append(i[4])



    ###################### Паттерны (настройки) для сборок####################

    tdpIndex = 0.7 # индекс на который tdp кулера должен превышать процессорный, по формуле tdp+tdp*0.5
    ramType = 'DDR4' # тип актуальной оперативной памяти
    recCountRAM = 8  # рекомендуемый размер оперативной памяти для одной планки по умолчанию
    recCountHDD = 1000 # рекомаендуемый размер HDD по умолчанию
    recCountSSD = 120 # рекомаендуемый размер SSD по умолчанию
    needFindVideo = True # флаг для поиска видеокарт в других ценовых категориях ввиду отсутствия их на рынке.
    companyCPU = [' ','AMD','Intel']
    companyVideo = [' ','GeForce','Radeon']


    resultBuild = []        # массив для окончательной сборки
    generateBuild = []      # массив для генерируемых сборок
    idResultBuild = []      # идентификаторы окончательной сборки
    comboIndex = 1          # индекс для комбинации сборок
    stopBuild = False       # аварийное завершение сборщика, в случае если не удаётся найти комплектующие (как правило связано с кризисом видеокарт)

    for comboCPUindex in companyCPU:
        for comboVideoindex in companyVideo:
            stopBuild = False
            for generalprice in range(30000,150000,1000):


                if generalprice <= 40000:
                    maxCpuProc = 0.24
                    maxVideoPrice = 0.24
                    maxRamPrice = 0.13
                    maxMotherPrice = 0.18
                    maxHddPrice = 0.1
                    maxSSDPrice = 0     # не нужен
                    maxBlockPrice = 0.09
                    maxcoolerprice = 0.03

                    recCountRAM = 4


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

                elif generalprice > 50000 and generalprice <= 60000:
                    maxCpuProc = 0.24
                    maxVideoPrice = 0.35
                    maxRamPrice = 0.1
                    maxMotherPrice = 0.11
                    maxHddPrice = 0.06
                    maxSSDPrice = 0.05
                    maxBlockPrice = 0.08
                    maxcoolerprice = 0.02

                    recCountHDD = 1000
                    recCountSSD=240

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
                    recCountSSD=240

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
                elif generalprice > 100000 and generalprice <= 150000:
                    maxCpuProc = 0.22
                    maxVideoPrice = 0.36
                    maxRamPrice = 0.1
                    maxMotherPrice = 0.1
                    maxHddPrice = 0.035
                    maxSSDPrice = 0.085
                    maxBlockPrice = 0.06
                    maxcoolerprice = 0.04

                    recCountHDD = 1000
                    recCountRAM = 16
                    recCountSSD = 960

                else:   # больше 150к  # свободных 2 процента
                    maxCpuProc = 0.19
                    maxVideoPrice = 0.40
                    maxRamPrice = 0.07
                    maxMotherPrice = 0.11
                    maxHddPrice = 0.03
                    maxSSDPrice = 0.07
                    maxBlockPrice = 0.06
                    maxcoolerprice = 0.05

                    recCountHDD = 2000
                    recCountRAM = 16
                    recCountSSD = 960


                maxCpuPrice =generalprice*maxCpuProc
                maxVideoPrice *=generalprice
                maxRamPrice *=generalprice
                maxMotherPrice *=generalprice
                maxHddPrice *=generalprice
                maxSSDPrice *=generalprice
                maxBlockPrice *=generalprice
                maxcoolerprice *=generalprice


                minCpuPrice = maxCpuPrice*0.7
                minVideoPrice = maxVideoPrice*0.9
                minRamPrice = maxRamPrice*0.65
                minMotherPrice = maxMotherPrice*0.7
                minHddPrice = maxHddPrice*0.7
                minSSDPrice = maxSSDPrice*0.5
                minBlockPrice = maxBlockPrice*0.8
                mincoolerprice = maxcoolerprice*0.6

                k = 0
                resultprice = 0  # результирующая стоимость сборки

                while resultprice/generalprice<0.9:

                    resultprice=0

                    generateBuild.clear()



                    ############### Поиск ЦПУ
                    max = 0     # для поиска максимального по benchrating комплектующего (далее аналогично)
                    cpuIndex = 0


                    for i in range(len(cpu_name)):
                        if (cpu_bench[i]!=None and cpu_bench[i]>max and 'OEM' in cpu_name[i] and comboCPUindex in cpu_name[i] and cpu_price[i]<=maxCpuPrice and cpu_price[i]>=minCpuPrice):
                            max = cpu_bench[i]
                            cpuIndex = i


                    maxCpuPrice +=50



                    generateBuild.append([cpu_name[cpuIndex],cpu_tdp[cpuIndex],cpu_socket[cpuIndex],cpu_price[cpuIndex]])
                    resultprice+=cpu_price[cpuIndex]


                    ################### Поиск Видеокарты
                    max=0
                    videoIndex=0


                    if needFindVideo==True:         # если ситуация с видеокартами кризисная
                        while videoIndex==0:

                            for i in range(len(video_name)):

                                if (video_bench[i] != None and video_bench[i]>max and video_price[i]<=maxVideoPrice and comboVideoindex in video_name[i] and video_price[i]>minVideoPrice):
                                    max = video_bench[i]
                                    videoIndex = i

                            minVideoPrice-=50

                            if minVideoPrice<0:
                                break
                    else:
                        for i in range(len(video_name)):

                            if (video_bench[i] != None and video_bench[i] > max and video_price[i] <= maxVideoPrice and comboVideoindex in video_name[i] and video_price[i] > minVideoPrice):
                                max = video_bench[i]
                                videoIndex = i


                    maxVideoPrice+=50


                    generateBuild[k].extend((video_name[videoIndex],video_price[videoIndex]))
                    resultprice+=video_price[videoIndex]




                    ################### Поиск Материнки
                    max = 0
                    motherIndex = 0


                    for i in range(len(mother_name)):
                        if (cpu_socket[cpuIndex]==mother_socket[i] and mother_ramname[i]==ramType and mother_dnsrate[i]>max and mother_price[i]<=maxMotherPrice and mother_price[i]>=minMotherPrice):
                            max = mother_dnsrate[i]
                            motherIndex=i

                    generateBuild[k].extend((mother_name[motherIndex], mother_ramname[motherIndex], mother_rampower[motherIndex], mother_price[motherIndex]))
                    resultprice += mother_price[motherIndex]

                    maxMotherPrice+=50
                    #################### Поиск ОЗУ
                    max=0
                    ramIndex = 0


                    for i in range(len(ram_name)):
                        if ram_socket[i]==mother_ramname[motherIndex] and ram_dnsrating[i]>max and ram_price[i]>=minRamPrice and ((ram_count[i]>=2 and ram_memory[i]==recCountRAM and ram_price[i]<=maxRamPrice) or (ram_count[i]==1 and ram_memory[i]==recCountRAM and ram_price[i]*2<=maxRamPrice)):
                            max = ram_dnsrating[i]
                            ramIndex = i

                    if ram_count[ramIndex]==1:      # если в комплекте 1 планка, то удваиваем цену и количество т.к берём по две.
                        generateBuild[k].extend((ram_name[ramIndex], ram_count[ramIndex]*2, ram_price[ramIndex]*2))
                        resultprice += ram_price[ramIndex]
                    else:
                        generateBuild[k].extend((ram_name[ramIndex], ram_count[ramIndex], ram_price[ramIndex]))
                        resultprice += ram_price[ramIndex]

                    maxRamPrice+=50

                    ###################### Поиск HDD
                    max = 0
                    hddIndex = 0

                    for i in range(len(hdd_name)):

                        if (hdd_dnsrating[i] > max and hdd_price[i]<=maxHddPrice and hdd_size[i]==recCountHDD and hdd_price[i]>=minHddPrice):
                            max = hdd_dnsrating[i]
                            hddIndex = i

                    generateBuild[k].extend((hdd_name[hddIndex], hdd_size[hddIndex], hdd_price[hddIndex]))
                    resultprice+=hdd_price[hddIndex]

                    maxHddPrice+=50

                    ###################### Поиск SSD
                    max = 0
                    ssdIndex = 0

                    for i in range(len(ssd_name)):
                        if (ssd_dnsrating[i] > max and ssd_size[i]>=recCountSSD and ssd_size[i]<=recCountSSD+60 and ssd_price[i] <= maxSSDPrice and ssd_price[i] >= minSSDPrice):
                            max = ssd_dnsrating[i]
                            ssdIndex = i

                    if maxSSDPrice!=0:
                        generateBuild[k].extend((ssd_name[ssdIndex], ssd_price[ssdIndex]))
                        resultprice += ssd_price[ssdIndex]

                    maxSSDPrice+=50
                    ####################### Поиск БП


                    max = 0
                    blockIndex = 0

                    for i in range(len(block_name)):
                        if (block_dnsrating[i] > max and block_power[i]>=video_blockwatt[videoIndex] and block_power[i]<=video_blockwatt[videoIndex]+100 and block_price[i]<=maxBlockPrice and block_price[i]>=minBlockPrice):
                            max = block_dnsrating[i]
                            blockIndex = i

                    generateBuild[k].extend((block_name[blockIndex],block_power[blockIndex],block_price[blockIndex]))
                    resultprice+=block_price[blockIndex]

                    maxBlockPrice+=50
                    ######################## Поиск кулера

                    max = 0
                    coolerIndex = 0

                    for i in range(len(cooler_name)):
                        if (cooler_dnsrating[i] > max and cooler_watt[i]>=cpu_tdp[cpuIndex]+cpu_tdp[cpuIndex]*tdpIndex and cooler_price[i]<=maxcoolerprice and cooler_price[i]>=mincoolerprice): # учет TDP, рейтинга ДНС и диапозона цен
                            max = cooler_dnsrating[i]
                            coolerIndex = i

                    generateBuild[k].extend((cooler_name[coolerIndex], cooler_watt[coolerIndex], cooler_price[coolerIndex]))
                    resultprice+=cooler_price[coolerIndex]

                    maxcoolerprice+=50


                    if maxVideoPrice*0.7>generalprice:      # если цена на любое комплектующее (н-р видеокарта) начинает превышать искомую цену, значит уходим в бесконечность и завершаем работу в текущей итерации.
                        stopBuild=True
                        break

                if stopBuild == True:       # завершаем работу по поиску комплектующих для текущей комбинации
                    break



                k += 1


                resultBuild.extend(generateBuild)
                idResultBuild.append([cpu_id[cpuIndex],video_id[videoIndex],mother_id[motherIndex],ram_id[ramIndex],hdd_id[hddIndex],ssd_id[ssdIndex],block_id[blockIndex],cooler_id[blockIndex],comboIndex,resultprice])
                print('Индекс',comboIndex,'Стоимость',resultprice,'Целевая',generalprice,'Сборка',generateBuild)

            comboIndex += 1


            conn = psycopg2.connect(dbname='postgres', user='postgres',
                                         password='29886622ss', host='localhost')
            cursor = conn.cursor()

            cursor.execute("set schema 'scraper'; truncate allbuilds RESTART IDENTITY")

            rowName = []
            cursor.execute(
                "select column_name from information_schema.columns where table_name = 'allbuilds' and table_schema = 'scraper';")


            for i in cursor.fetchall():  # формирование списка столбцов    последнюю колонку не считаем, т.к там rating
                if i[0]!='id':
                    rowName.append(i[0])



            d = {}  # dict словарь
            for i in range(len(idResultBuild)):
                for j in range(len(rowName)):
                    d.update({rowName[j]: idResultBuild[i][j]})

                sql = "set schema 'scraper'; insert into allBuilds ({columns}) VALUES {values};".format(  # Инсёртим данные
                    columns=', '.join(d.keys()),
                    values=tuple(d.values())
                )

                cursor.execute(sql)

            conn.commit()





if __name__ == "__main__":

    getBuilds()

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

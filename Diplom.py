import time
import re
import requests
from bs4 import BeautifulSoup as BS
import psycopg2
from fake_headers import Headers
from requests.exceptions import TooManyRedirects

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

        print (self.session.headers)



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

        self.cursor.execute("set schema 'scraper'; truncate {0}".format(
            self.tableName))  # ОЧИСТКА ТАБЛИЦЫ!!! При медленной работы переделать на UPDATE!!

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
                    productID[i - 1]) + '"}}'
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




        print (r.text)
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
        self.urlrate = urlrate  # ссылка на сайт с рейтингом


        self.startScraper(validateName,validateID,tableName)

    def getAdditional(self):


        self.lineName.extend([self.productName, self.SocketName, self.PowerName, self.CountCPUs, self.price, self.dnsrate])  # объединение списков в один список для коммита последующего



        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
            result = result[0].text
            matchSocket = re.search(r'\[(.*?)\,', result)
            matchPower = re.search(r'x(.*?)М', result)
            matchCountCpus = re.search(r', \d{1,2}', result)

            self.SocketName.append(matchSocket.group()[1:-1])
            self.PowerName.append(matchPower.group()[2:-2])
            self.CountCPUs.append(matchCountCpus.group()[2:])



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
        self.urlrate = urlrate # ссылка на сайт с рейтингом


        self.startScraper(validateName,validateID,tableName)

    def getAdditional(self):
        self.lineName = [self.productName, self.SocketName, self.PowerName, self.VideoRAM, self.VideoBus, self.price,
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

        self.startScraper(validateName, validateID, tableName)

    def getAdditional(self):


        self.lineName = [self.productName, self.WriteSSD,self.ReadSSD, self.price,
                         self.dnsrate]  # список строк для коммита в таблицу
        for el in self.html.select('.product-info'):
            result = el.select('.product-info__title > span')
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

    cpu_name = []
    cpu_socket = []
    cpu_price = []
    cpu_bench = []
    cpu_dnsrate = []

    for i in cursor.fetchall():
        cpu_name.append(i[1])
        cpu_socket.append(i[2])
        cpu_price.append(i[5])
        cpu_dnsrate.append(i[6])
        cpu_bench.append(i[7])

    cursor.execute("set schema 'scraper'; select * from video;")

    video_name = []
    video_socket = []
    video_price = []
    video_bench = []
    video_dnsrate = []

    for i in cursor.fetchall():
        video_name.append(i[1])
        video_socket.append(i[2])
        video_price.append(i[6])
        video_dnsrate.append(i[7])
        video_bench.append(i[8])

    cursor.execute("set schema 'scraper'; select * from mother;")

    mother_name = []
    mother_socket = []
    mother_slotsram = []
    mother_ramname = []
    mother_price = []
    mother_chipset = []
    mother_dnsrate = []
    mother_rampower = []

    for i in cursor.fetchall():
        mother_name.append(i[1])
        mother_socket.append(i[2])
        mother_slotsram.append(i[3])
        mother_ramname.append(i[4])
        mother_rampower.append(i[5])
        mother_price.append(i[6])
        mother_chipset.append(i[7])
        mother_dnsrate.append(i[8])

    cursor.execute("set schema 'scraper'; select * from ram;")

    ram_name = []
    ram_socket = []
    ram_count = []
    ram_memory = []
    ram_price = []
    ram_dnsrating = []
    ram_power = []

    for i in cursor.fetchall():
        ram_name.append(i[1])
        ram_socket.append(i[2])
        ram_power.append(i[3])
        ram_count.append(i[4])
        ram_memory.append(i[5])
        ram_price.append(i[6])
        ram_dnsrating.append(i[7])

    cursor.execute("set schema 'scraper'; select * from block;")

    block_name = []
    block_price = []
    block_dnsrating = []
    block_power = []

    for i in cursor.fetchall():
        block_name.append(i[1])
        block_power.append(i[2])
        block_price.append(i[3])
        block_dnsrating.append(i[4])

    cursor.execute("set schema 'scraper'; select * from ssd;")

    ssd_name = []
    ssd_price = []
    ssd_dnsrating = []

    for i in cursor.fetchall():
        ssd_name.append(i[1])
        ssd_price.append(i[4])
        ssd_dnsrating.append(i[5])

    cursor.execute("set schema 'scraper'; select * from hdd;")

    hdd_name = []
    hdd_size = []
    hdd_price = []
    hdd_dnsrating = []

    for i in cursor.fetchall():
        hdd_name.append(i[1])
        hdd_size.append(i[2])
        hdd_price.append(i[3])
        hdd_dnsrating.append(i[4])

    cursor.execute("set schema 'scraper'; select * from cooler;")

    cooler_name = []
    cooler_watt = []
    cooler_price = []
    cooler_dnsrating = []

    for i in cursor.fetchall():
        cooler_name.append(i[1])
        cooler_watt.append(i[2])
        cooler_price.append(i[3])
        cooler_dnsrating.append(i[4])



    # Паттерны для сборок

    recCountRAM = 16  # рекомендуемый размер оперативной памяти
    recCountHDD = 1000 # рекомаендуемый размер HDD
    recCountSSD = 500 # рекомаендуемый размер SSD


    for generalprice in range(41000,50000,1000):

        resultbuilds = []



        if generalprice <= 40000:
            maxCpuPrice = 0.2
            maxVideoPrice = 0.29
            maxRamPrice = 0.13
            maxMotherPrice = 0.14
            maxHddPrice = 0.09
            maxSSDPrice = 0     # не нужен
            maxBlockPrice = 0.09
            maxcoolerprice = 0.02



        elif generalprice > 40000 and generalprice <= 50000:
            maxCpuPrice = 0.21
            maxVideoPrice = 0.33
            maxRamPrice = 0.12
            maxMotherPrice = 0.13
            maxHddPrice = 0.07
            maxSSDPrice = 0.05
            maxBlockPrice = 0.07
            maxcoolerprice = 0.02

            recCountHDD = 1000

        elif generalprice > 50000 and generalprice <= 60000:
            maxCpuPrice = 0.24
            maxVideoPrice = 0.36
            maxRamPrice = 0.1
            maxMotherPrice = 0.1
            maxHddPrice = 0.05
            maxSSDPrice = 0.05
            maxBlockPrice = 0.08
            maxcoolerprice = 0.02

            recCountHDD = 1000
        elif generalprice > 60000 and generalprice <= 70000:
            maxCpuPrice = 0.23
            maxVideoPrice = 0.36
            maxRamPrice = 0.09
            maxMotherPrice = 0.12
            maxHddPrice = 0.05
            maxSSDPrice = 0.04
            maxBlockPrice = 0.09
            maxcoolerprice = 0.02

            recCountHDD = 1000
        elif generalprice > 70000 and generalprice <= 100000:
            maxCpuPrice = 0.22
            maxVideoPrice = 0.37
            maxRamPrice = 0.1
            maxMotherPrice = 0.1
            maxHddPrice = 0.04
            maxSSDPrice = 0.07
            maxBlockPrice = 0.08
            maxcoolerprice = 0.02

            recCountHDD = 2000
        elif generalprice > 100000 and generalprice <= 150000:
            maxCpuPrice = 0.23
            maxVideoPrice = 0.40
            maxRamPrice = 0.08
            maxMotherPrice = 0.1
            maxHddPrice = 0.04
            maxSSDPrice = 0.05
            maxBlockPrice = 0.06
            maxcoolerprice = 0.04

            recCountHDD = 2000
            recCountRAM = 32

        else:   # больше 150к
            maxCpuPrice = 0.19
            maxVideoPrice = 0.41
            maxRamPrice = 0.07
            maxMotherPrice = 0.11
            maxHddPrice = 0.04
            maxSSDPrice = 0.05
            maxBlockPrice = 0.06
            maxcoolerprice = 0.07

            recCountHDD = 4000
            recCountRAM = 32

        maxCpuPrice *=generalprice
        maxVideoPrice *=generalprice
        maxRamPrice *=generalprice
        maxMotherPrice *=generalprice
        maxHddPrice *=generalprice
        maxSSDPrice *=generalprice
        maxBlockPrice *=generalprice
        maxcoolerprice *=generalprice

        minCpuPrice = maxCpuPrice*0.8
        minVideoPrice = maxVideoPrice*0.8
        minRamPrice = maxRamPrice*0.2
        minMotherPrice = maxMotherPrice*0.7
        minHddPrice = maxHddPrice*0.5
        minSSDPrice = maxSSDPrice*0.5
        minBlockPrice = maxBlockPrice*0.6
        mincoolerprice = maxcoolerprice*0.5


        print (maxHddPrice)
        flag = 1 # где 1 - кулер, 2 - БП , 3 - HDD 4 - mother, 5 - ОЗУ, 6 - CPU + Video

        k=0



        resultprice = 0             # результирующая стоимость сборки

        ############### Поиск ЦПУ
        max = 0     # для поиска максимального по benchrating комплектующего (далее аналогично)


        for i in range(len(cpu_name)):
            if (cpu_bench[i]>max and cpu_price[i]<maxCpuPrice and cpu_price[i]>minCpuPrice):
                max = cpu_bench[i]
                cpuIndex = i



        resultbuilds.append([cpu_name[cpuIndex],cpu_socket[cpuIndex],cpu_price[cpuIndex]])
        resultprice+=cpu_price[cpuIndex]


        ################### Поиск Видеокарты
        max=0


        for i in range(len(video_name)):
            if (video_bench[i] != None and video_bench[i]>max and video_price[i]<maxVideoPrice and video_price[i]>minVideoPrice):
                max = video_bench[i]
                videoIndex = i
        resultbuilds[k].extend((video_name[videoIndex],video_price[videoIndex]))
        resultprice+=video_price[videoIndex]




        ################### Поиск Материнки
        max = 0
        motherIndex = 0

        for i in range(len(mother_name)):

            if (resultbuilds[k][1]==mother_socket[i] and mother_dnsrate[i]>max and mother_price[i]<=maxMotherPrice and mother_price[i]>=minMotherPrice):
                max = mother_dnsrate[i]
                motherIndex=i

        resultbuilds[k].extend((mother_name[motherIndex], mother_ramname[motherIndex], mother_rampower[motherIndex],
                                mother_price[motherIndex]))
        resultprice += mother_price[motherIndex]


        #################### Поиск ОЗУ
        max=0
        ramIndex = 0

        for i in range(len(ram_name)):
            #if ram_memory[i]==recCountRAM/2 and ram_count[i]==1 and ram_price[i]>=minRamPrice:
                #print (ram_price[i])
            if ram_socket[i]==resultbuilds[k][6] and ram_dnsrating[i]>max and ram_price[i]>=minRamPrice and ((ram_count[i]>=2 and ram_memory[i]==recCountRAM and ram_price[i]<=maxRamPrice) or (ram_count[i]==1 and ram_memory[i]==recCountRAM/2 and ram_price[i]*2<=maxRamPrice)):
                max = ram_dnsrating[i]
                ramIndex = i


        resultbuilds[k].extend((ram_name[ramIndex], ram_count[ramIndex], ram_price[ramIndex]))
        resultprice += ram_price[ramIndex]


        ###################### Поиск HDD
        max = 0
        hddIndex = 0

        for i in range(len(hdd_name)):
            if (hdd_dnsrating[i] > max and hdd_price[i]<=maxHddPrice and hdd_size[i]==recCountHDD and hdd_price[i]>=minHddPrice):
                max = hdd_dnsrating[i]
                hddIndex = i

        resultbuilds[k].extend((hdd_name[hddIndex], hdd_size[hddIndex], hdd_price[hddIndex]))
        resultprice+=hdd_price[hddIndex]

        ###################### Поиск SSD
        max = 0
        ssdIndex = 0

        for i in range(len(hdd_name)):
            if (ssd_dnsrating[i] > max and ssd_price[i] <= maxSSDPrice and ssd_price[i] >= minSSDPrice):
                max = hdd_dnsrating[i]
                hddIndex = i

        if maxSSDPrice!=0:
            resultbuilds[k].extend((ssd_name[hddIndex], ssd_price[hddIndex]))
            resultprice += ssd_price[ssdIndex]


        ####################### Поиск БП


        max = 0

        for i in range(len(block_name)):
            if (block_dnsrating[i] > max and block_price[i]<=maxBlockPrice and block_price[i]>=minBlockPrice):
                max = block_dnsrating[i]
                blockIndex = i

        resultbuilds[k].extend((block_name[blockIndex],block_power[blockIndex],block_price[blockIndex]))
        resultprice+=block_price[blockIndex]


        ######################## Поиск кулера

        max = 0

        for i in range(len(cooler_name)):
            if (cooler_dnsrating[i] > max and cooler_price[i]<=maxcoolerprice and cooler_price[i]>=mincoolerprice):
                max = cooler_dnsrating[i]
                coolerIndex = i

        resultbuilds[k].extend((cooler_name[coolerIndex], cooler_watt[coolerIndex], cooler_price[coolerIndex]))
        resultprice+=cooler_price[coolerIndex]


        resultbuilds[k].append(resultprice)

        #print (resultbuilds[k],generalprice,flag)

        #time.sleep(0.5)
        #k += 1


        print("Итоговая сборка: ", resultbuilds[-1])
        print ('Стоимость',resultprice,'Цель',generalprice,'Расхождение',resultprice/generalprice)












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

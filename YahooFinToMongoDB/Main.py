from bson import binary
from yahoo_fin.stock_info import *
from tqdm import *
from pymongo import *
import json
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import pickle
from keras.utils import np_utils
import tensorflow as tf


def getTokenBullMarket(dni,password):
    url = "https://bullmarketbrokers.com/Home/Login"

    payload = {
        'idNumber': str(dni),
        'password': password
    }

    headers = {
      'Cookie': 'ASP.NET_SessionId=et443mc4ngbnfe5suw541bhf; 7572a1cd-608b-45e4-b6a7-fdb52f674e8c=UserId=UJhud7cd59jbcDYUz0dLvw==; lastUserIdLogged=lastUserIdLogged=113203; notificationCookie=notifications={"type1":[],"type2":[]}'
    }

    response = requests.request("POST", url, headers=headers, data = payload)

    response = response.text.encode('utf-8')
    response = json.loads(response)

    if response['succeed']:
        return response['token']
    return 'Failure'


def getCedearsFrom(tickets):
    ticketsAvaliables = []
    for ticket in tqdm(range(len(tickets))):
        ticketActual = tickets[ticket]
        try:
            data = get_data(ticketActual + ".ba",start_date="24/08/2020")
            ticketsAvaliables.append(ticketActual + ".ba")
        except:
            continue
    return ticketsAvaliables


def updateTicketsCedears(mongoClientUsed):
    cedears = []
    decicion = input("¿Quiere obtener los cedears de dow jones? dow jones tiene " + str(len(tickers_dow())) + " acciones en total: ")
    if(decicion == "y"):
        print("obteniendo cedears de dow jones")
        cedears += getCedearsFrom(tickers_dow())
    decicion = input("¿Quiere obtener los cedears de nasdaq? nasdaq tiene " + str(len(tickers_nasdaq())) + " acciones en total: ")
    if(decicion == "y"):
        print("obteniendo cedears de nasdaq")
        cedears += getCedearsFrom(tickers_nasdaq())
    decicion = input("¿Quiere obtener los cedears de sp500? sp500 tiene " + str(len(tickers_sp500())) + " acciones en total: ")
    if(decicion == "y"):
        print("obteniendo cedears de sp500")
        cedears += getCedearsFrom(tickers_sp500())

    myclient = MongoClient(mongoClientUsed)
    mydb = myclient["Market"]
    mycol = mydb["ticketsCedears"]

    for ticket in mycol.find():
        for ticketActual in range(len(cedears)):
            if (ticket["TicketName"] == cedears[ticketActual]):
                cedears.pop(ticketActual)
                break
        if len(cedears) == 0:
            break

    for ticket in cedears:
        mydict = { "TicketName": ticket}
        x = mycol.insert_one(mydict)


def getInfoFewDaysAgo(days, actualDate, ticket):
    date_N_days_ago = actualDate - timedelta(days=days)
    dateInStringStart = date_N_days_ago.strftime("%m/%d/%Y")
    dateInStringEnd = actualDate.strftime("%m/%d/%Y")
    try:
        data = get_data(ticket, start_date=dateInStringStart,end_date=dateInStringEnd)
    except:
        data = "failure"

    return data


def getBollingerBands(days, actualDate, ticket):
    data = getInfoFewDaysAgo(days, actualDate, ticket)
    if type(data) != type("") :
        standarsDesviations = []
        totalDays = data['open'].to_numpy().__len__()
        dataPastTest = getInfoFewDaysAgo(days*2, actualDate, ticket)
        for day in range(totalDays):
            dataPast = dataPastTest.iloc[day:totalDays+day]
            promediosPast = dataPast.loc[:, ['open', 'close', 'high', 'low']]
            standarsDesviations.append(np.std(promediosPast.mean(1).to_numpy()))
        aux = data.loc[:, ['open', 'close', 'high', 'low']]
        BollingerBand = {
            'prom': aux.mean(1).to_numpy(),
            "standarDesviation": standarsDesviations
        }
        return True, BollingerBand
    else:
        return False, None


def acotation(max, min, num):
    if (max - min) < 1:
        return int(((num - min) / 1) * 99)
    return int(((num - min) / (max - min)) * 99)


def comparation(rangeEquality, firstNumber, secondNumber):
    if secondNumber > firstNumber - 5 and secondNumber < firstNumber:
        return 3
    elif secondNumber > firstNumber - 10 and secondNumber <= firstNumber - 5:
        return 2
    elif secondNumber > firstNumber - 20 and secondNumber <= firstNumber - 10:
        return 1
    elif secondNumber <= firstNumber - 20:
        return 0

    if secondNumber < firstNumber + 5 and secondNumber >= firstNumber:
        return 4
    elif secondNumber < firstNumber + 10 and secondNumber >= firstNumber + 5:
        return 5
    elif secondNumber < firstNumber + 20 and secondNumber >= firstNumber + 10:
        return 6
    elif secondNumber >= firstNumber + 20:
        return 7


def createTrainsDataCedears(dateToStart):
    DAYS = 30

    date_time = datetime.fromisoformat(dateToStart)
    xTrains = []
    yTrains = []
    yTest = []
    xTest = []
    cedears = []
    for cedear in mycol.find():
        cedears.append(cedear['TicketName'])
    trainOrTest = True
    for NroCedear in tqdm(range(30)):
        if NroCedear == 27:
            continue
        cedearTicket = cedears[NroCedear]
        prom = getInfoFewDaysAgo(1, date_time + timedelta(days=1), cedearTicket)
        if type(prom) != type("") :
            prom = [prom["open"][0], prom["close"][0], prom["high"][0], prom["low"][0]]
            prom = np.mean(prom)
            data = getInfoFewDaysAgo(DAYS, date_time, cedearTicket)
            Bands = getBollingerBands(DAYS, date_time, cedearTicket)
            xQuantity = len(Bands['prom'])
            heatMap = np.zeros((100, xQuantity))
            for xPos in range(xQuantity):
                yPos = acotation(np.max(data['high']), np.min(data['low']), Bands['prom'][xPos])
                yPosClose = acotation(np.max(data['high']), np.min(data['low']), data['close'][xPos])
                yPosOpen = acotation(np.max(data['high']), np.min(data['low']), data['open'][xPos])
                if yPos >= 100:
                    yPos = 99
                if yPosClose >= 100:
                    yPosClose = 99
                if yPosOpen >= 100:
                    yPosOpen = 99

                if yPosOpen < yPosClose:
                    heat = 100
                    plus = 80 / (yPosClose - yPosOpen)
                    for y in range(yPosOpen, yPosClose):
                        heatMap[y][xPos] = int(heat)
                        heat += plus
                elif yPosClose < yPosOpen:
                    heat = 180
                    substrac = 80 / (yPosOpen - yPosClose)
                    for y in range(yPosClose, yPosOpen):
                        heatMap[y][xPos] = int(heat)
                        heat -= substrac
                heatMap[yPos][xPos] = 255
            acotationVar = acotation(np.max(data["high"]), np.min(data["low"]), prom)
            if acotationVar >= 100:
                acotationVar = 99
            elif acotationVar < 0:
                acotationVar = 0
            if trainOrTest:
                yTrains.append(acotationVar)
                xTrains.append(heatMap.copy())
            else:
                yTest.append(acotationVar)
                xTest.append(heatMap.copy())
            trainOrTest = not trainOrTest
            plt.imshow(heatMap, cmap='hot', interpolation='nearest')
            plt.show()
    xTrains = np.array(xTrains)
    yTrains = np.array(yTrains)
    xTest = np.array(xTest)
    yTest = np.array(yTest)

    return xTrains, yTrains, xTest, yTest


def runIATest():
    xTrains, yTrains, xTest, yTest = createTrainsDataCedears("2020-08-26")

    # adapt the data
    xTrains = xTrains.reshape((xTrains.shape[0], xTrains.shape[1] * xTrains.shape[2]))
    xTest = xTest.reshape((xTest.shape[0], xTest.shape[1] * xTest.shape[2]))

    xTrains = xTrains / 255
    xTest = xTest / 255

    yTrains = np_utils.to_categorical(yTrains, 100)
    yTest = np_utils.to_categorical(yTest, 100)

    # create the model

    class MyModel(tf.keras.Model):

        def __init__(self):
            super(MyModel, self).__init__()
            self.dense1 = tf.keras.layers.Dense(32, input_dim=2100, activation=tf.nn.relu)
            self.dense2 = tf.keras.layers.Dense(100, activation=tf.nn.softmax)
            self.dropout = tf.keras.layers.Dropout(0.5)

        def call(self, inputs):
            x = self.dense1(inputs)
            return self.dense2(x)

    # use the model

    model = MyModel()

    model.compile(optimizer='sgd', loss='categorical_crossentropy', metrics=['accuracy'])

    model.fit(x=xTrains, y=yTrains, batch_size=100, epochs=10, verbose=1, validation_data=(xTest, yTest))

    evaluacion = model.evaluate(x=xTest, y=yTest, batch_size=100, verbose=1)

    print(yTest)
    print(evaluacion)

myclient = MongoClient("mongodb://localhost:27017/")


mydb = myclient["Market"]
mycol = mydb["ticketsCedears"]
myData = mydb["cedearData"]
myOtherData = mydb["cedearPureData"]

# updateTicketsCedears("mongodb://localhost:27017/")

# get de heatMap (just 2 cedears for now)
cedears = []
for ticket in mycol.find():
    cedears.append(ticket['TicketName'])

updateInfo = {
    "fecha":datetime.now().strftime("%m/%d/%Y"),
    "cedears":[]
}
for cedear in cedears:
    info = getInfoFewDaysAgo(1,datetime.now(),cedear)
    if type(info) != type("") :
        infoToUpdate = {
            "ticket": cedear,
            "open":info["open"][0],
            "close":info["close"][0],
            "high":info["high"][0],
            "low":info["low"][0]
        }
        updateInfo["cedears"].append(infoToUpdate.copy())
nro = 0
for a in myOtherData.find({"fecha": datetime.now().strftime("%m/%d/%Y")}):
    nro += 1
if nro > 0:
    myOtherData.update_one({"fecha": datetime.now().strftime("%m/%d/%Y")}, { "$set": { "cedears": updateInfo["cedears"] } })
else:
    myOtherData.insert_one(updateInfo)




"""
#save in database

for mapAndResult in range(len(xTrains)):
    mydict = {
        "heatmap": binary.Binary(pickle.dumps(xTrains[mapAndResult], protocol=2)),
        "result": int(yTrains[mapAndResult])
    }
    x = myData.insert_one(mydict)
"""


"""
------------------------------------------------
runIATest()

Description:
run a IA's Test
------------------------------------------------
getBollingerBands(ticket)

Description:
Give you the bollinger bands in a dict
 
The dict returned:
bollingerBand{
    prom:[],
    standarDesviation:[]
}
------------------------------------------------
getInfoFewDaysAgo(days,actualDate,ticket)

Description:
return the data from few days ago
------------------------------------------------
updateTicketsCedears(mongoClientUsed)

Description: 
Update the name of cedears's tickets in the database
------------------------------------------------
getCedearsFrom(tickets)

Description:
check in an array if it have valids cedears and give you the truly tickets
------------------------------------------------
getTokenBullMarket(dni,password)

Description:
with the dni and the password of an account in BullMarket give you a valid token 
"""
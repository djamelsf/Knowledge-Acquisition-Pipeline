from flask import Flask, render_template, redirect, url_for, request, Response
import requests
import os
import time
import requests
from bs4 import BeautifulSoup as bs
import psycopg2
import json
import sys
import subprocess
from multiprocessing import Process
import re
import textract



"""
Recuperation d'un texte a partir d'un Lien (découpage en paragraphes)
"""
def getTextFromLink(url):
    article = requests.get(url)  
    soup = bs(article.content, "html.parser")
    body= soup.find("body")
    text = [p.text for p in body.find_all("p")] 
    return text

"""
Recuperation d'un texte a partir d'un fichier PDF (découpage en paragraphes)
"""
def getTextFromFile(file):
    text = textract.process(os.path.join("upload", file.filename))
    text=text.decode("utf-8")
    text=text.split('\n\n')
    return text

"""
Extraction des entités avec l'API DBPedia Spotlight
"""
def getNED(text):
    t=[]
    for p in text:
        headers = {
        'accept': 'application/json',
        }
        
        params = (
        ('text', p),
        )
        response=requests.get('https://api.dbpedia-spotlight.org/en/candidates', headers=headers, params=params)
        try:
            responses = response.json()
            for line in responses['annotation']['surfaceForm']:
                tup=(line['@name'],line['resource']['@uri'])
                if tup not in t:
                    t.append(tup)
        except ValueError:
            pass
        except TypeError:
            pass
        except KeyError:
            pass
    return t


"""
Extraction des types en utilisant la base de données Postgres (yagoTransitiveType)
"""
def getTypes(t):
    HOST = "localhost"
    USER = "admin"
    PASSWORD = ""
    DATABASE = "ka"
    connection = psycopg2.connect(user="DJAM",password="",host="127.0.0.1",port="5432",database="ka")
    cursor = connection.cursor()
    data={}
    for i in t:
        sql = "select object from yagoFacts where subject = '<"+i[1].replace("'", "''")+">' and object like '<wordnet_%>';"
        cursor.execute(sql)
        res=cursor.fetchall()
        tab=[]
        for y in res:
            tab.append(y[0])
        data[i[0]]=tab
    return data



"""
Ordonner les données (TopType,Types[])
"""
def orderByTopType(data):
    print('----------->DEBUT')
    t1={}
    t2={}
    t3={}
    t4={}
    t5={}
    for i in data:
        for j in data.get(i):
            if 'person' in j:
                if i not in t1:
                    t1[i]=data.get(i)
            else:
                if 'organization' in j:
                    if i not in t2:
                        t2[i]=data.get(i)
                else:
                    if 'event' in j:
                        if i not in t3:
                            t3[i]=data.get(i)
                    else:
                        if 'artifact' in j:
                            if i not in t4:
                                t4[i]=data.get(i)
                        else:
                            if 'yagogeoentity' in j:
                                    if i not in t5:
                                        t5[i]=data.get(i)
    topt={}
    if bool(t1):
        topt['person']=t1
    if bool(t2):
        topt['organization']=t2
    if bool(t3):
        topt['event']=t3
    if bool(t4):
        topt['artifact']=t4
    if bool(t5):
        topt['yagogeoentity']=t5
    print('----------->FIN')
    return topt


"""
Conversion de chaine, exemple:  "<wordnet_player_110439851>" ---------> "player"
"""
def typetoString(type):
    pattern = "_(.*?)_"
    substring = re.search(pattern, type).group(1)
    return substring



"""
Utilisation du Framework PURE, extraction des types les plus représentatifs
(Appel parallel au framework PURE)
"""
def pure(data):
    data=orderByTopType(data)
    tabP=[]
    for i in data:
        with open(i+'.json', 'w') as f:
            json.dump(data[i], f)
            p=Process(target=subprocess.call, args=(['python', 'run.py', i, i+".json","100"],))
            tabP.append(p)
            p.start()

    for j in tabP:
        j.join()

    res={}
    for i in data:
        with open(i+"/predicted_file.json") as json_file:
            d = json.load(json_file)
            res.update(d)

    for i in res:
        for j in range(0,len(res[i])):
            res[i][j]=typetoString(res[i][j])

    return res


"""
Pipeline
"""
def pipline(text):
    entity=getNED(text)
    data=getTypes(entity)
    return pure(data)





app = Flask(__name__)





@app.route("/")
def home():
	return render_template("home.html")

@app.route("/link",methods=["POST","GET"])
def link():
	if request.method == "POST":
		link=request.form["link"]
		res=pipline(getTextFromLink(link))
		return render_template("view.html",res=res)
	else:
		return render_template("link.html")

@app.route("/file",methods=["POST", "GET"])
def file():
    if request.method == "POST":
        file=request.files["file"]
        file.save(os.path.join("upload", file.filename))
        data=getTextFromFile(file)
        res=pipline(data)
        return render_template("view.html",res=res)
    return render_template("file.html")


if __name__ == "__main__":
    app.run()
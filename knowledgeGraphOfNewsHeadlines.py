from neo4j.v1 import GraphDatabase
import urllib.request
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
import requests
import spacy
import en_core_web_sm
import re

#Fetch News from News API
def fetchNews():
    url = 'https://newsapi.org/v2/top-headlines?country=in&apiKey='+"Insert your API Key here"
    response = requests.get(url)

    news = []
    for articles in response.json()["articles"]:
        if(articles["description"] != None and len(articles["description"]) < 257):
            news.append(articles["description"])
    return news

#Check if a wikipedia page exists for your entity
def checkIfArticleExists(str):
    try:
        a = urllib.request.urlopen("https://en.wikipedia.org/wiki/"+str).getcode()
        if(a == 200):
            return True
    except:
        return False

#Returns the list of entitites whose wikipedia article exists
def checkEntitites(list):
    result = []
    for entity in list:
        if(checkIfArticleExists(entity) == True):
            result.append(entity)
    return result

#Write the contents of news headlines to file
def writeToFile(list):
    file = open('filename.txt','w',encoding='utf-8')
    for items in list:
        file.write(items+'\n')

#Remove redundant data from news headlines
def textPreProcessing(str):
    result = []
    nlp = en_core_web_sm.load()
    doc = nlp(str)
    for ents in doc.ents:
    	if ents.label_ not in {"DATE","MONEY","CARDINAL"}:
    		result.append(re.sub(r"[^a-zA-Z0-9]+", ' ', ents.text))
    return result

#Connect to neo4j driver/database running on your system 
driver = GraphDatabase.driver("bolt://localhost", auth=("username","password"))
session = driver.session()

#clear the database if any existing data is present
clearQuery = "MATCH (n) DETACH DELETE(n)"
session.run(clearQuery)

#indexing queries which helps the further operations run smoother
createID_IndexQuery = "CREATE INDEX ON :Category(catId)"
createNameIndexQuery = "CREATE INDEX ON :Category(catName)"
createPageTitleQuery = "CREATE INDEX ON :Page(pageTitle)"
session.run(createID_IndexQuery)
session.run(createNameIndexQuery)
session.run(createPageTitleQuery)

#fetch news - News headlines are updated every 15 minutes or so
news = fetchNews()
writeToFile(news)

#iterate through news headlines
for string in news:
    entities = textPreProcessing(string)
    realEntities = checkEntitites(entities)

    for entity in realEntities:
        createRootCategoryQuery = "MERGE (c:Category {catId: 0, catName:" +"'"+entity+"',"+ "subcatsFetched : false, pagesFetched : false, level: 0 })"
        session.run(createRootCategoryQuery)

    for first, second in zip(realEntities,realEntities[1:]):
        addRelationshipQuery = "MATCH (a:Category{catName:'"+first+"'}),(b:Category{catName:'"+second+"'}) CREATE (a)-[r:related]->(b) Return r"
        session.run(addRelationshipQuery)

#Root nodes of Knowledge Graph Created
print("ROOT CATEGORIES CREATED")

#Increase the knowledge by creating a wikipedia category graph of each entity/node in knowledge graph
finalQuery = 'UNWIND range(0,1) as level CALL apoc.cypher.doIt(" MATCH (c:Category { subcatsFetched: false, level: $level}) CALL apoc.load.json('+"'https://en.wikipedia.org/w/api.php?format=json&action=query&list=categorymembers&cmtype=subcat&cmtitle=Category:'"+' + apoc.text.urlencode(c.catName) + '"'&cmprop=ids%7Ctitle&cmlimit=500'"+') YIELD value as results UNWIND results.query.categorymembers AS subcat MERGE (sc:Category {catId: subcat.pageid}) ON CREATE SET sc.catName = substring(subcat.title,9),sc.subcatsFetched = false,sc.pagesFetched = false,sc.level = $level + 1 WITH sc,c CALL apoc.create.addLabels(sc,['+"'Level'"+' +  ($level + 1) + '+"'Category'"+']) YIELD node MERGE (sc)-[:SUBCAT_OF]->(c) WITH DISTINCT c SET c.subcatsFetched = true", { level: level }) YIELD value RETURN value'
session.run(finalQuery)

print("Knowledge Graph has been formed")

session.close()

print("Program Terminated Successfully")

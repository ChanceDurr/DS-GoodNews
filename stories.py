import feedparser
from collections import OrderedDict
from database import Database
import json
import datetime
import random
import keras
import signal
from flask import g
from sklearn.externals import joblib
from scipy.sparse import hstack
from keras.models import load_model

global svm, mnb, lr, rf, nn, tfidf_vectorizer_text, tfidf_vectorizer_pos

with open('svm.pkl', 'rb') as f:
    svm = joblib.load(f)
with open('mnb.pkl', 'rb') as f:
    mnb = joblib.load(f)
with open('lr.pkl', 'rb') as f:
    lr = joblib.load(f)
with open('rf.pkl', 'rb') as f:
    rf = joblib.load(f)
with open('neural_net.h5', 'rb') as f:
    nn = load_model('neural_net.h5')

with open('tfidf_vectorizer_pos.pkl', 'rb') as f:
    tfidf_vectorizer_pos = joblib.load(f)
with open('tfidf_vectorizer_text.pkl', 'rb') as f:
    tfidf_vectorizer_text = joblib.load(f)

print('models loaded')

class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)

def update():
    
    return update_files()

def update_feeds(list_of_RSS_feeds):
    """ takes a list RSS feeds, a list containing article urls from the feeds, and a list containing
    the last update times of each feed. Returns an updated list of article urls and an updated list
    of last update times""" 
    list_of_article_urls = []
    for RSS_feed in list_of_RSS_feeds:
        feed = feedparser.parse(RSS_feed)
        for item in feed["items"]:
            list_of_article_urls.append(item['id'])

    return random.choices(population=list_of_article_urls, k=5)



from newspaper import Article
import nltk
import hashlib
# nltk.download('punkt')

def newspaperize(article_url):
    """Takes an article url and an id number. Returns a dictionary containing information scraped
    from the article"""

    article = Article(article_url)

    print("Downloading:", article_url)

    try:
        with timeout(seconds=2):
            article.download()
    except:
        print("Failed to download url:", article_url)
        return None, None, None

    try:
        article.parse()
    except:
        print("Failed to parse url:", article_url)
        return None, None, None

    headline = article.title
    imageurl = article.top_image
    timestamp = article.publish_date
    content = article.text
    article.nlp()
    keywords = article.keywords
    summary = article.summary
    description = article.meta_description
    id_number = hashlib.sha1(article_url.encode('utf-8')).hexdigest()
    clickbait = classify_clickbait(headline)
    # timestamp can be None
   
    # article_information = {"id" : id_number,
    #               "name": headline,
    #               "url" : article_url,
    #               "timestamp" : timestamp.isoformat() if timestamp is not None else "",
    #               "description" : description,
    #               "keywords" : keywords,
    #               "summary" : summary,
    #               "content" : content,
    #               "clickbait" : None}
    article_information = OrderedDict([
                  ("id" , id_number),
                  ("name", headline),
                  ("imageurl", imageurl),
                  ("url" , article_url),
                  ("timestamp" , timestamp.isoformat() if timestamp is not None else ""),
                  ("description" , description),
                  ("keywords" , keywords),
                  ("summary" , summary),
                  ("content" , content),
                  ("clickbait" , clickbait),
                  ("createtime" , str(datetime.datetime.now()))
    ])


    article_list = list(article_information.values())
    article_list[6] = ','.join(keywords)
    keyword_list = []
    for word in keywords:
        keyword_list.append( [article_information["id"], word])
    return article_information, article_list, keyword_list


import pandas as pd

def classify_clickbait(headline):
    
    def getPosTags(text):
        posTags = nltk.pos_tag(nltk.word_tokenize(text))
        justTags = []
        for tags in posTags:
            justTags.append(tags[1])
        return justTags
    
    # with open('svm.pkl', 'rb') as f:
    #     svm = joblib.load(f)
    # with open('mnb.pkl', 'rb') as f:
    #     mnb = joblib.load(f)
    # with open('lr.pkl', 'rb') as f:
    #     lr = joblib.load(f)
    # with open('rf.pkl', 'rb') as f:
    #     rf = joblib.load(f)
    # with open('neural_net.h5', 'rb') as f:
    #     nn = load_model('neural_net.h5')

    # with open('tfidf_vectorizer_pos.pkl', 'rb') as f:
    #     tfidf_vectorizer_pos = joblib.load(f)
    # with open('tfidf_vectorizer_text.pkl', 'rb') as f:
    #     tfidf_vectorizer_text = joblib.load(f)
    
    # print('models loaded')
    
    headline_pos = getPosTags(headline)
    headline_pos = ' '.join([str(tag) for tag in headline_pos])

    data_tfidf_text = tfidf_vectorizer_text.transform([headline])
    data_tfidf_pos = tfidf_vectorizer_pos.transform([headline_pos])

    data_tfidf = hstack([data_tfidf_pos, data_tfidf_text]).toarray()
    data_tfidf = pd.DataFrame(data_tfidf)

    nn_pred = nn.predict(data_tfidf)
    nn_pred = [0 if i < 0.5 else 1 for i in nn_pred][0]

    predictions = [int(svm.predict(data_tfidf)[0]),
                   int(mnb.predict(data_tfidf)[0]),
                   int(lr.predict(data_tfidf)[0]),
                   int(rf.predict(data_tfidf)[0]),
                   nn_pred]

    return max(set(predictions), key=predictions.count)

import jsonlines

def newspaperize_new_articles_from_feed(new_article_urls):

    new_article_jsons = []
    new_article_list = []
    new_article_keywords_lists = []
    print('begin downloading and processing')
    for article_url in new_article_urls:
        article_json, article_list, keyword_list = newspaperize(article_url)
        print('finished all downloading and processing')
        if article_json is not None:
            new_article_jsons.append(article_json)
            new_article_list.append(article_list)
            new_article_keywords_lists += keyword_list
    print('newspaperize new articles complete')
    return new_article_jsons, new_article_list, new_article_keywords_lists

def update_files():

    with open('RSS_feeds.txt') as f:
        list_of_RSS_feeds = f.readlines()
    with open('extracted_article_urls.txt') as f:
        extracted_article_urls = f.readlines()

    updated_article_urls = update_feeds(list_of_RSS_feeds)

    new_article_urls = list(set(updated_article_urls).difference(extracted_article_urls))

    new_article_jsons, new_article_list, new_article_keywords_lists = newspaperize_new_articles_from_feed(new_article_urls)
    print('before db writes')
    # write to database
    db = Database('goodnews.db')
    db.connect()
    db.insert(new_article_list,new_article_keywords_lists)
    print('after db writes')
    with open('extracted_article_urls.txt', 'a') as f:
        for url in new_article_urls:
            f.write(url + '\n')

    # output to jsonlines
    with jsonlines.open('articles.jsonl', mode = 'a') as f:
        for article_json in new_article_jsons: 
            f.write(article_json)

    return json.dumps(new_article_jsons)

def readall():
    db = Database('goodnews.db')
    db.connect()
    stories = db.read()
    list_dict_stories = []
    for s in stories:
        article_information = OrderedDict([
                            ("id" , s[0]),
                            ("name", s[1]),
                            ("imageurl", s[2]),
                            ("url" , s[3]),
                            ("timestamp" , s[4]),
                            ("description" , s[5]),
                            ("keywords" , s[6].split(',')),
                            ("summary" , s[7]),
                            ("content" , s[8]),
                            ("clickbait" , s[9]),
                            ("createtime" , s[10])
                            ])
        list_dict_stories.append(article_information)

    return json.dumps(list_dict_stories)
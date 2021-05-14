import json
import os
import time

from flask import Flask, jsonify, redirect, request, url_for
from flask_cors import CORS
import requests
from textblob import TextBlob
import numpy as np
import pandas as pd
import re
import matplotlib.pyplot as plt
plt.style.use('fivethirtyeight')
import praw
import geocoder
from datetime import datetime, timedelta
import urllib
from timeit import default_timer as tim
from configs import Configs
from twitter import TwitterAPI

# configuration
DEBUG = True


# instantiate the app
app = Flask(__name__)
app.config.from_object(__name__)
app.config['TESTING'] = True

# enable CORS
CORS(app, resources={r'/*': {'origins': '*'}})

#Getting data from TWITTER
def auth():
    return os.environ.get("BEARER_TOKEN")

def create_recent_search_url(query, start_time=None, next_token=None):
    tweet_fields = "tweet.fields=public_metrics,created_at,geo,referenced_tweets,text,author_id,id,in_reply_to_user_id"
    max_results = "max_results=100"
    user_fields = "user.fields=profile_image_url"
    
    url = "https://api.twitter.com/2/tweets/search/recent?query={}&{}&{}&{}".format(
        query, tweet_fields, user_fields ,max_results)
    
    if start_time:
        url += "&start_time={}".format(start_time)
    
    if next_token:
        url += "&next_token={}".format(next_token)
    
    return url

def create_id_url(ids):
    tweet_fields = "tweet.fields=public_metrics,created_at,geo,lang,referenced_tweets,text,author_id,in_reply_to_user_id"
    user_fields = "user.fields=profile_image_url"
    url = "https://api.twitter.com/2/tweets?ids={}&{}&{}".format(
        ",".join(ids), tweet_fields, user_fields)
    return url

def create_users_url(user_ids):
    user_fields= "user.fields=location,name,profile_image_url,public_metrics,username,verified"
    url = "https://api.twitter.com/2/users?ids={}&{}".format(
        ",".join(user_ids), user_fields)
    return url

def create_headers(bearer_token):
    headers = {"Authorization": Configs["bearer_token"]}
    return headers

def twitter_recent_search(url, headers):
    response = requests.request("GET", url, headers=headers)
    if response.status_code != 200:
        raise Exception(response.status_code, response.text)
    return response.json()


# TODO: can work on callback later
@app.route('/callback', methods=['GET'])
def callback():
    d = request.json
    print(d)
    return "OK"

@app.route('/auth/request_token', methods=['GET'])
def request_token():
    consumer_key= Configs["consumer_key"]
    consumer_secret= Configs["consumer_secret"]
    client = TwitterAPI(consumer_key, consumer_secret)
    key, secret = client.requestAccessToken()
    return json.dumps({
        "request_key": key.decode("unicode_escape"),
        "request_secret": secret.decode("unicode_escape")
    })

@app.route('/auth/access_token', methods=['POST'])
def get_user_access_token():
    consumer_key= Configs["consumer_key"]
    consumer_secret= Configs["consumer_secret"]
    client = TwitterAPI(consumer_key, consumer_secret)
    d = request.json
    print(d)
    key, secret = client.getAccessToken(d["request_key"], d["request_secret"], d["verifier"])
    return json.dumps({
        "access_key": key.decode("unicode_escape"),
        "access_secret": secret.decode("unicode_escape")
        #now it´s autherized. now, store the keys.
    })


#start-page for backend
@app.route('/')
def startpage():
    return "Backend up and running!"

@app.route('/reddit/search', methods=['GET', 'POST'])
def reddit_search():
#how long does it take to run this function? using start = tim() to start timer
    start = tim()
    d = request.json
    print(d)
    json_response = {"data":{}}

    #Reddit API call, time displayed in unix
    reddit_data = reddit_api(d["query"])

    if len(reddit_data) != 0:
        try:
            piechartreddit = reddit_piechart(reddit_data)
            linechartreddit = reddit_linechart(reddit_data)
            reddit_data = sorted(reddit_data, key = lambda i: i['upvotes'],reverse=True)
            engagementreddit = reddit_engagement(reddit_data)
            toppostsreddit = reddit_top_posts(reddit_data)
            topusersreddit = reddit_top_users(reddit_data)
            wordcloudreddit = reddit_wordcloud(reddit_data)
        except Exception as e:
            print(e)  

    else:
        print("No Reddit data")
        json_response["data"] = "No data"
        piechartreddit = []
        linechartreddit = {}
        engagementreddit = {}
        toppostsreddit = []
        topusersreddit = []
        wordcloudreddit = []

    if json_response["data"] != "No data":        
        json_response["data"] = {
            d["query"]: {
                "query": d["query"], 
                "engagementreddit": engagementreddit, 
                "piechartreddit": piechartreddit, 
                "linechartreddit":linechartreddit,
                "toppostsreddit": toppostsreddit, 
                "topusersreddit": topusersreddit, 
                "wordcloudreddit": wordcloudreddit
            }
        }

    end = tim()
    result = end-start
    print("IT TOOK THIS AMOUNT OF TIME IN REDDIT-search: ", result)
    return json.dumps(json_response)


@app.route('/twitter/search', methods=['GET', 'POST'])
def twitter_search():
    #start timer 
    start = tim()
    d = request.json    
    unencoded_query = str(d["query"])

    unavailable_chars = ['$', '*', "'", '&', "‘"]
 
    for i in unavailable_chars :
        unencoded_query = unencoded_query.replace(i, '')
    
    
    query = urllib.parse.quote(unencoded_query)

    #Create the token to get acess to the Twitter 
    bearer_token = auth()
    headers = create_headers(bearer_token)

    tweets = get_tweets(query, headers)
    if len(tweets) == 0: 
        return json.dumps({"data": "No data"})
    
    # add retweets to the results
    ids = extract_retweet_ids(tweets)
    for i in range(0, len(ids), 100):
        ids_url = create_id_url(ids[i:i+100])
        response = twitter_recent_search(ids_url, headers)
        for i in response.get("data", []):
                tweets[i["id"]] = i

    users_info = retrieve_user_info(tweets, headers)

    # Create all of the data that is going to be displayed in the frontend from the tweet datas
    barchart = create_barchart(tweets)
    linechart = create_linechart(tweets)
    topposts = create_topposts(tweets, users_info)
    topusers = create_topusers(users_info)
    activity = create_activity(tweets)
    links = create_links(tweets, users_info)
    nodes = create_nodes(links)
    geochart = create_geochart(tweets)
    all_texts = all_text(tweets)
    sentiment = show_tweets_text_sentiment(all_texts)

    end = tim()
    result_time = end-start
    print("TWITTER SEARCH(500) TOOK IN SECONDS: ", result_time)
    return json.dumps({
        "data": {
            d["query"]: {
            "barchart": barchart, 
            "linechart": linechart, 
            "topposts": topposts, 
            "topusers": topusers, 
            "activity": activity, 
            "query": d["query"], 
            "nodes": nodes, 
            "links": links, 
            "geochart": geochart,
            "sentiment": sentiment
        }
    }})


# get tweets matching the query in the last week (max 500 tweets)
def get_tweets(query, headers):

    start_time = datetime.utcnow() - timedelta(weeks=1)
    start_time = start_time.replace(microsecond=0).isoformat() + "Z"

    tweets = {}

    search_url = create_recent_search_url(query, start_time, None)
    
    response = twitter_recent_search(search_url, headers)
    
    for i in response.get("data", []):
        tweets[i["id"]] = i

    # max result of tweets retrieved can be set here: 
    while response.get("meta", {}).get("next_token") != None and len(tweets) < 500:
        search_url = create_recent_search_url(query, None, response["meta"]["next_token"])
        response = twitter_recent_search(search_url, headers)
        for i in response.get("data", []):
            tweets[i["id"]] = i
    return tweets


#Function for extracting the data about the orginal tweets that was retweeted. 
#The reasoning behind this is because the twitter search api returns alot of retweets of an orignal tweet.
#And when the api returns a retweet you only get the retweets not the likes, quotes or the replies of the orginal tweet.
#So we call the api for the orignal tweets that we extract from the retweets.
def extract_retweet_ids(tweets):
    id_set = set()
    joined_string = []

    for id_, data in tweets.items():
        if "referenced_tweets" in data:
            if data["referenced_tweets"][0]["type"] == "retweeted":
                id_set.add(data["referenced_tweets"][0]["id"])

    return list(id_set)

#Function for extracting all off the usernames and calling the API for every 100 tweet.
#Returning all of the user data that is missing from the first API call.
#With this function we get the location and stats like how many followers a user has.xz z
def retrieve_user_info(tweets, headers):
    users_info = {}
    users_ids = set()
    for id_, data in tweets.items():
        users_ids.add(data["author_id"])
    
    users_ids = list(users_ids)
    
    for i in range(0, len(users_ids), 100):
        users_url = create_users_url(users_ids[i:i+100])
        response = twitter_recent_search(users_url, headers)
        for i in response.get("data", []):
            users_info[i["id"]] = i

    return users_info


# Function to extract the total likes, retweets, replies and quotes. The API return the total retweets of the original tweet is a user has retweeted it.
# So the function does not count the retweets of a retweet. Only the retweets of the orignal tweet
def create_barchart(tweets):
    total_retweets = 0
    total_likes = 0
    total_replies = 0
    total_quotes = 0

    for id_, data in tweets.items():
        if "referenced_tweets" in data:
            if data['referenced_tweets'][0]["type"] != "retweeted":
                total_retweets += data['public_metrics']["retweet_count"]
                total_likes += data['public_metrics']["like_count"]
                total_replies += data['public_metrics']["reply_count"]
                total_quotes += data['public_metrics']["quote_count"]
        else:
              total_retweets += data['public_metrics']["retweet_count"]
              total_likes += data['public_metrics']["like_count"]
              total_quotes += data['public_metrics']["quote_count"]
              total_replies += data['public_metrics']["reply_count"]
       
    barchartlist = [['Likes', total_likes], ['Retweeets', total_retweets],['Replies', total_replies],['Quotes',total_quotes]]

    return barchartlist

# Function to make a list that is needed to display the areachart   
def create_linechart(tweets):
    allDates = []
    finalDates = {}
    

    for id_, data in tweets.items():
        allDates.append(data["created_at"].replace(".000Z", ""))

    allDates.sort() 
    allDates = allDates[10:]

    for i in range(len(allDates)):
        finalDates[allDates[i]] = i+1
    
    return finalDates

#Function that returns the dates from when a person retweets a tweet
def create_retweet_linechart(json_response):
    tweets = json_response["data"]
    allDates = []
    finalDates = []
      
    for i in range(len(tweets)):
        if "referenced_tweets" in tweets[i]:
              if tweets[i]['referenced_tweets'][0]["type"] == "retweeted":
                    element = tweets[i]["created_at"]
                    allDates.append(element)
 

    for i in range(len(tweets)):
        allDates[i] = allDates[i].replace(".000Z", "")

    allDates.sort() 
    allDates = allDates[5:]
    
    for i in range(len(allDates)):
        finalDates.append([allDates[i],i+1])
          
    return finalDates

# Function the extract the top 3 post and returns a dictonary with all the data needed to display as a tweet
def create_topposts(tweets, users_info):
    print("This is all the tweets: ",tweets)
    print("This is the user_info: ", users_info)
    topposts = []
    # sorting based on retweet_count 
    tweets_sorted = sorted(tweets.values(), key = lambda i: i['public_metrics']["retweet_count"],reverse=True)

    for data in tweets_sorted:
        if "referenced_tweets" not in data:
            date = format_date(data["created_at"])
            topposts.append({
                "author_id": data["author_id"], 
                "retweets": data['public_metrics']["retweet_count"], 
                "likes": data['public_metrics']["like_count"], 
                "text": data['text'],
                "username": users_info[data["author_id"]]["username"], 
                "img": users_info[data["author_id"]]["profile_image_url"], 
                "date": date, 
                "followers": users_info[data["author_id"]]["public_metrics"]["followers_count"], 
                "verified": users_info[data["author_id"]]["verified"], 
                "id": data["id"]
            })
            if len(topposts) == 3:
                break
    return topposts


# Maybe add functionality that returns day and month like 13 Feb...
def format_date(timestamp):
    ts = time.strptime(timestamp[:19], "%Y-%m-%dT%H:%M:%S")
    s = time.strftime("%m/%d/%Y", ts)
    return s

# Function for extracting the top 9 users with the most followers with a check that is not added 
def create_topusers(users_info):
    # print(users_info)
    topusers = {}
    # sorting data before sending 
    sorted_topusers = sorted(users_info.values(), key=lambda i: i['public_metrics']["followers_count"], reverse=True)
    for data in sorted_topusers:
        if data["username"] not in data:
            topusers[data["username"]] = {
                "username": data["username"],
                "img": data["profile_image_url"], 
                "followers": data['public_metrics']["followers_count"], 
                "verified": data["verified"]
            }
            if len(topusers) == 9:
                break

    print("SORTED TOP USERS: ", sorted_topusers)
    return topusers

#Function to extact the data displayed in the yellow header. Returning a dictionary with the total posts, users and engagement
#Users is only users that is posting something not a user that is retweeting. Total posts is the total tweets, replies and quotes. 
#Engangement is likes and retweets
def create_activity(tweets):
    activity = {}
    user_ids = []
    engagement = 0 
    total_posts = 0
    for id_, data in tweets.items():
        if "referenced_tweets" in data:
              if data['referenced_tweets'][0]["type"] != "retweeted":
                  engagement += data['public_metrics']["retweet_count"]
                  engagement += data['public_metrics']["like_count"]
                  total_posts += 1   
                  if data["author_id"] not in user_ids:
                      user_ids.append(data["author_id"])          
        else:
              engagement += data['public_metrics']["retweet_count"]
              engagement += data['public_metrics']["like_count"]
              total_posts += 1
              if data["author_id"] not in user_ids:
                      user_ids.append(data["author_id"])
            
    activity["posts"] = total_posts
    activity["users"] = len(user_ids)
    activity["engagement"] = engagement

    return activity

def create_links(tweets,users_info):

    links = []

    for id_, data in tweets.items():
        if "referenced_tweets" in data:
            if data['referenced_tweets'][0]["type"] == "retweeted":
                text = data['text']
                idxAt = text.find('@')
                idxCo = text.find(':')
                followers = users_info[data["author_id"]]["public_metrics"]["followers_count"]

                if followers <= 10000:
                    size = 3
                elif followers <= 50000:
                    size = 5
                elif followers <= 100000:
                    size = 7
                elif followers <= 1000000:
                    size = 10
                elif followers > 1000000:
                    size = 13
            
                links.append({'source': text[idxAt+1:idxCo], 'target': users_info[data["author_id"]]["username"], 'size':size})

            elif data['referenced_tweets'][0]["type"] == "replied_to":
                text = data['text']
                idxAt = text.find('@')
                idxS = text.find(' ')
                followers = users_info[data["author_id"]]["public_metrics"]["followers_count"]

                if followers <= 10000:
                    size = 3
                elif followers <= 50000:
                    size = 5
                elif followers <= 100000:
                    size = 7
                elif followers <= 1000000:
                    size = 10
                elif followers > 1000000:
                    size = 13

                links.append({'source': text[idxAt+1:idxS], 'target': users_info[data["author_id"]]["username"], 'size':size})

    return links


def create_nodes(links):
    nodes = []
    for i in range(len(links)):
        if links[i]['source'] not in nodes:
            nodes.append({"id":links[i]['source'], 'size':links[i]['size']})
        
        if links[i]['target'] not in nodes:
            nodes.append({"id":links[i]['target'], 'size':links[i]['size'] })
    return nodes

#Legg inn en error catcher her for geochart kommer ofte feil når det er en query med lite resultater
def create_geochart(tweets):
    all_locations = []
    
    for id_, data in tweets.items():
        if "location" in data:
            all_locations.append(data["location"])
            if len(all_locations) == 99:
                break
 
    all_countries = []

    try:
        g = geocoder.mapquest(all_locations, method='batch', key=Configs["mapquest_key"])
        for result in g:
            all_countries.append(str(result.country))
            
        geochart = dict((x,all_countries.count(x)) for x in set(all_countries))
    except:
        geochart = {}

    return geochart

def all_text(tweets):
    texts = []
    for id_, data in tweets.items():
        texts.append(data["text"])
    return texts

#  Print tweet text
def show_tweets_text_sentiment(all_texts):      
    # Create a dataframe with a column called Tweets
    df = pd.DataFrame(columns=['Tweets'])
    for tweet in all_texts:
        cleantweet = cleanTxt(tweet)
        df = df.append({"Tweets": cleantweet}, ignore_index=True)
   
    # Create two new columns 'Subjectivity' & 'Polarity'
    df['Subjectivity'] = df['Tweets'].apply(getSubjectivity)
    df['Polarity'] = df['Tweets'].apply(getPolarity)
    df['Analysis'] = df['Polarity'].apply(getAnalysis)
    pd.set_option('display.max_rows', df.shape[0]+1)
    dictionaryObject = df.to_dict()

    sentiment = {"Positive": 0, "Negative": 0, "Neutral": 0}

    analysis = dictionaryObject["Analysis"]


    for i in range(len(analysis)):
        if analysis[i] == "Positive":
            sentiment["Positive"] += 1
        elif analysis[i] == "Negative":
            sentiment["Negative"] += 1
        else:
            sentiment["Neutral"] += 1
          
    return sentiment
    
# Create a function to clean the tweets
def cleanTxt(text):
    text = re.sub('@[A-Za-z0–9]+', '', text) #Removing @mentions
    text = re.sub('#', '', text) # Removing '#' hash tag
    text = re.sub('RT[\s]+', '', text) # Removing RT
    text = re.sub('https?:\/\/\S+', '', text) # Removing hyperlink
    
    return text

# A function to get the subjectivity
def getSubjectivity(text):
   return TextBlob(text).sentiment.subjectivity

# A function to get the polarity
def getPolarity(text):
   return  TextBlob(text).sentiment.polarity

# function to compute negative (-1), neutral (0) and positive (+1) analysis
def getAnalysis(score):
    if score < 0:
        return 'Negative'
    elif score == 0:
        return 'Neutral'
    else:
        return 'Positive'
    


def reddit_api(query):
    reddit_data = []
    #Reddit API call, time displayed in unix
    reddit = praw.Reddit(
    client_id=Configs["client_id"],
    client_secret=Configs["client_secret"],
    user_agent="my user agent")

    for submission in reddit.subreddit("all").search(query, limit=100):
        try:
            reddit_data.append({"author": str(submission.author.name), "title": str(submission.title),"name": str(submission.name), "upvote_ratio": submission.upvote_ratio, "upvotes": submission.ups,
            "url": str(submission.permalink), "created_at": str(submission.created_utc), "subreddit": str(submission.subreddit), "number_of_comments": str(submission.num_comments),
            "post_karma": submission.author.link_karma, "comment_karma": submission.author.comment_karma, "icon_img": submission.author.icon_img})
        except:
            print("User suspended")
   
    print(reddit_data)
    return reddit_data


def reddit_piechart(reddit_data):
    ratio_sum = 0
    for i in range(len(reddit_data)):
        ratio_sum += reddit_data[i]["upvote_ratio"]
    
    upvote_ratio = round(ratio_sum/len(reddit_data),2)

    downvote_ratio = round(1-upvote_ratio,2)

    ratio = [["Upvote Percentage", upvote_ratio*100], ["Downvote Percentage", downvote_ratio*100]] 

    return ratio

def reddit_wordcloud(reddit_data):
    wordcloud = {}
    for i in range(len(reddit_data)):
        subreddit = reddit_data[i]["subreddit"]
        if subreddit not in wordcloud:
            wordcloud[subreddit] = 1
        else:
            wordcloud[subreddit] += 1

    wordcloud_list = []
    for value in wordcloud.keys():
        if wordcloud[value]>1:
            if wordcloud[value] <= 3:
                wordcloud_list.append({"subreddit": value, "value": 1})
            elif wordcloud[value] <= 6:
                wordcloud_list.append({"subreddit": value, "value": 2})
            elif wordcloud[value] <= 10:
                wordcloud_list.append({"subreddit": value, "value": 3})
            elif wordcloud[value] <= 20:
                wordcloud_list.append({"subreddit": value, "value": 4})
            else:
                wordcloud_list.append({"subreddit": value, "value": 5})
                

    return wordcloud_list
            
def reddit_linechart(reddit_data):
    allDates = []
    finalDates = {}

    for i in range(len(reddit_data)):
        timestamp = reddit_data[i]["created_at"]
        
        timestamp = timestamp.replace(".0", "")
        
        allDates.append(datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%dT%H:%M:%S'))
        
    allDates.sort() 
   

    for i in range(len(allDates)):
        finalDates[allDates[i]]=i+1    
    return finalDates
          
def reddit_top_posts(reddit_data):
    top_posts = []
    for i in range(len(reddit_data)):
        top_post = {}
        top_post["title"] = reddit_data[i]["title"]
        top_post["url"] = reddit_data[i]["url"]
        top_post["title"] = reddit_data[i]["title"]
        top_post["author"] = reddit_data[i]["author"]
        top_post["upvotes"] = reddit_data[i]["upvotes"]
        top_post["icon_img"] = reddit_data[i]["icon_img"]
        top_post["subreddit"] = reddit_data[i]["subreddit"]
        top_post["number_of_comments"] = reddit_data[i]["number_of_comments"]
        timestamp = reddit_data[i]["created_at"]
        timestamp = timestamp.replace(".0", "")
        top_post["created_at"]= datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d')
        top_posts.append(top_post)
        if len(top_posts) == 3:
            break



    return top_posts

def reddit_top_users(reddit_data):
    reddit_data = sorted(reddit_data, key = lambda i: i['post_karma'],reverse=True)
    top_users = []
    for i in range(len(reddit_data)):
        top_user = {}
        top_user["author"] = reddit_data[i]["author"]
        top_user["post_karma"] = reddit_data[i]["post_karma"]
        top_user["comment_karma"] = reddit_data[i]["comment_karma"]
        top_user["icon_img"] = reddit_data[i]["icon_img"]
        if top_user not in top_users:
            top_users.append(top_user)
            if len(top_users) == 9:
                break

    return top_users

   
def reddit_engagement(reddit_data):
    engagement = {}
    
    user_ids = []
    upvotes = 0 

    for i in range(len(reddit_data)):
        upvotes += reddit_data[i]["upvotes"]
        if reddit_data[i]["author"] not in user_ids:
            user_ids.append(reddit_data[i]["author"]) 
    
    engagement["posts"] = len(reddit_data)
    engagement["users"] = len(user_ids)
    engagement["engagement"] = upvotes

    return  engagement


if __name__ == '__main__':
    app.run(debug=True, port=os.environ.get("PORT"))
"export FLASK_DEBUG=ON"

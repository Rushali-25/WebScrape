import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import openai  # Correctly import openai
import pandas as pd
import threading
import time
import schedule
from flask import Flask, jsonify, render_template
import os
from dotenv import load_dotenv
import plotly.express as px
import dash
from dash import dcc, html
import plotly.graph_objs as go
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY','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')
data_storage = [] 
lock = threading.Lock()
def scrape_wikipedia_business():
    base_url = "https://en.wikipedia.org/wiki/List_of_largest_companies_by_revenue"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"Error scraping Wikipedia Business: {e}")
        return
    leads = []
    for company_row in soup.select("table.wikitable tbody tr"):
        columns = company_row.find_all("td")
        if len(columns) > 1:
            name = columns[1].get_text(strip=True)  
            if name:  
                leads.append({"name": name, "source": "Wikipedia"})
    print(f"Scraped {len(leads)} companies from Wikipedia.")
    with lock:
        data_storage.extend(leads)
def automated_google_search():
    search_query = "top trending businesses 2025"
    driver_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=driver_service)
    driver.get("https://www.google.com")
    
    search_box = driver.find_element(By.NAME, "q")
    search_box.send_keys(search_query)
    search_box.send_keys(Keys.RETURN)
    time.sleep(2)
    
    results = driver.find_elements(By.XPATH, "//div[@class='tF2Cxc']")
    leads = []
    for result in results:
        try:
            name = result.find_element(By.TAG_NAME, "h3").text
            url = result.find_element(By.TAG_NAME, "a").get_attribute("href")
            leads.append({"name": name, "url": url, "source": "Google"})
        except Exception as e:
            print(f"Error extracting data from Google result: {e}")
    
    print(f"Scraped {len(leads)} results from Google.") 
    
    driver.quit()
    
    with lock:
        data_storage.extend(leads)
app = Flask(__name__)

@app.route('/status', methods=['GET'])
def status():
    with lock:
        print(f"Data in storage: {len(data_storage)}")  
        if len(data_storage) == 0:
            print("No data available.")
        return jsonify({
            "total_leads": len(data_storage),
            "data": data_storage[:100]  
        })
def run_automation():
    scrape_wikipedia_business() 
    automated_google_search() 
    
    schedule.every(4).hours.do(scrape_wikipedia_business)
    schedule.every(6).hours.do(automated_google_search)

    while True:
        schedule.run_pending()
        time.sleep(1)

automation_thread = threading.Thread(target=run_automation, daemon=True)
automation_thread.start()
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dashboard/')

dash_app.layout = html.Div([
    html.H1("Top 10 Trending Companies Dashboard", style={'text-align': 'center'}),
    html.Div([
        html.H3("Top Companies Trend (Real-Time)"),
        dcc.Graph(id="top-companies-trend"),
        html.Hr(),
        html.H3("Trigger Data Fetching (Manual)"),
        html.Button('Fetch Data', id='fetch-data-button', n_clicks=0),
    ], style={'padding': '20px'}),
])

@dash_app.callback(
    dash.dependencies.Output('top-companies-trend', 'figure'),
    [dash.dependencies.Input('fetch-data-button', 'n_clicks')]
)
def update_dashboard(n_clicks):

    with lock:
 
        company_names = [lead['name'] for lead in data_storage]
        company_counts = pd.Series(company_names).value_counts().head(10)

        fig_company_trends = px.bar(company_counts, x=company_counts.index, y=company_counts.values,
                                    labels={'x': 'Company Name', 'y': 'Occurrences'},
                                    title="Top 10 Trending Companies")

    return fig_company_trends

if __name__ == "__main__":
    app.run(port=5000,debug=True)
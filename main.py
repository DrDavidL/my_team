# This will make two simultaneous requests to LLMs and reconcile with a 3rd LLM.

from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chat_models import ChatOpenAI
from langchain.chains import RetrievalQA
from langchain.embeddings.openai import OpenAIEmbeddings
# from langchain.callbacks.manager import CallbackManager
# from langchain.chains import QAGenerationChain
from langchain.vectorstores import FAISS
import streamlit as st
import openai
from openai import OpenAI
from prompts import *
import time
import concurrent.futures
import requests
import json
import datetime
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

client = OpenAI()
use_rag = False
use_snippets = False

@st.cache_data
def extract_domains(domains):
    """
    Function to extract domain names from a string.
    
    Parameters:
    domains (str): The string containing the domain names.

    Returns:
    list: A list of domain names.
    """
    # Split the string into individual sites
    sites = domains.split(' OR ')

    # Extract the domain name from each site
    domain_names = [site.replace('site:', '') for site in sites]

    return domain_names


@st.cache_data
def websearch_snippets(web_query, max):
    web_query = domains + " " + web_query
    api_url = "https://real-time-web-search.p.rapidapi.com/search"
    querystring = {"q":web_query,"limit":max}
    headers = {
        "X-RapidAPI-Key": st.secrets["X-RapidAPI-Key"],
        "X-RapidAPI-Host": "real-time-web-search.p.rapidapi.com"
    }

    response = requests.get(api_url, headers=headers, params=querystring)
    response_data = response.json()
    all_snippets = []
    urls = []
    for item in response_data['data']:
        all_snippets.append(f"{item['title']} {item['snippet']}  {item['url']}  <END OF SITE>" )
        urls.append(item['url'])
    

    # st.info("Web snippets reviewed.")
    st.write(f'HERE IS THE SNIPPETS RESPONSE: {all_snippets}')
    
    return all_snippets, urls

@st.cache_data
def join_and_clean_snippets(snippets, separator=' <END OF SITE> '):
    """
    Function to join snippets of HTML content from multiple sites into a single string, and then clean and split the joined HTML.
    
    Parameters:
    snippets (list): A list of HTML snippets.
    separator (str): The separator used to join the snippets.

    Returns:
    list: A list of paragraphs.
    """
    st.write(f'Here is the snippets input: {snippets}')
    # Join the snippets into a single string with the separator
    full_html = separator.join(snippets)

    # Clean and split the joined HTML
    paragraphs = clean_and_split_html(full_html, separator)

    return paragraphs

@st.cache_data
def clean_and_split_html(full_html, separator=' <END OF SITE> '):
    """
    Function to remove HTML tags from a string and split the cleaned text into paragraphs.
    
    Parameters:
    full_html (str): The HTML string to be cleaned and split.
    separator (str): The separator used to split the full_html into individual site contents.

    Returns:
    list: A list of paragraphs.
    """
    # Split the full_html into individual site contents
    site_contents = full_html.split(separator)

    # List of tags to consider when splitting the text
    tags = ['p', 'div', 'section', 'article', 'aside', 'details', 'figcaption', 'figure', 
            'footer', 'header', 'main', 'mark', 'nav', 'summary', 'time']

    all_paragraphs = []

    # Process each site's content individually
    for html in site_contents:
        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # Find all the tags in the HTML
        found_tags = soup.find_all(tags)

        # Extract the text from each tag and store in a list
        paragraphs = [tag.get_text(strip=True) for tag in found_tags]

        # If no tags were found, fall back to splitting the text by newline characters
        if not paragraphs:
            text = ' '.join(soup.stripped_strings).replace('\n', ' ').replace('\r', '')
            paragraphs = text.split('\n')

        all_paragraphs.extend(paragraphs)

    return all_paragraphs

@st.cache_resource
def set_llm_chat(model, temperature):
    if model == "openai/gpt-3.5-turbo":
        model = "gpt-3.5-turbo"
    if model == "openai/gpt-3.5-turbo-16k":
        model = "gpt-3.5-turbo-16k"
    if model == "openai/gpt-4":
        model = "gpt-4"
    if model == "openai/gpt-4-1106-preview":
        model = "gpt-4-1106-preview"
    if model == "gpt-4" or model == "gpt-3.5-turbo" or model == "gpt-3.5-turbo-16k" or model == "gpt-4-1106-preview":
        return ChatOpenAI(model=model, openai_api_base = "https://api.openai.com/v1/", openai_api_key = st.secrets["OPENAI_API_KEY"], temperature=temperature)
    else:
        headers={ "HTTP-Referer": "https://fsm-gpt-med-ed.streamlit.app", # To identify your app
          "X-Title": "GPT and Med Ed"}
        return ChatOpenAI(model = model, openai_api_base = "https://openrouter.ai/api/v1", openai_api_key = st.secrets["OPENROUTER_API_KEY"], temperature=temperature, max_tokens = 500, headers=headers)

@st.cache_resource
def create_retriever(texts):  
    
    embeddings = OpenAIEmbeddings(model = "text-embedding-ada-002",
                                  openai_api_base = "https://api.openai.com/v1/",
                                  openai_api_key = st.secrets['OPENAI_API_KEY']
                                  )
    try:
        vectorstore = FAISS.from_texts(texts, embeddings)
    except (IndexError, ValueError) as e:
        st.error(f"Error creating vectorstore: {e}")
        return
    retriever = vectorstore.as_retriever(k=5)

    return retriever

# @st.cache_data
# def split_texts(text, chunk_size, overlap, split_method):

#     text_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=chunk_size, chunk_overlap=overlap)

#     splits = text_splitter.split_text(text)
#     if not splits:
#         # st.error("Failed to split document")
#         st.stop()

#     return splits

@st.cache_resource
def prepare_rag(list, model):
    # splits = split_texts(text, chunk_size=1000, overlap=100, split_method="recursive")
    text = ' <END OF SITE> '.join(list)
    splits = clean_and_split_html(text)
    retriever = create_retriever(splits)
    llm = set_llm_chat(model=model, temperature=0.3)
    rag = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
    return rag

@st.cache_data
def websearch_learn(web_query: str, retrieval, scrape_method, max) -> float:
    """
    Obtains real-time search results from across the internet. 
    Supports all Google Advanced Search operators such (e.g. inurl:, site:, intitle:, etc).
    
    :param web_query: A search query, including any Google Advanced Search operators
    :type web_query: string
    :return: A list of search results
    :rtype: json
    
    """
    
    web_query = domains + " " + web_query
    # st.info(f'Here is the websearch input: **{web_query}**')
    url = "https://real-time-web-search.p.rapidapi.com/search"
    querystring = {"q":web_query,"limit":max}
    headers = {
        "X-RapidAPI-Key": st.secrets["X-RapidAPI-Key"],
        "X-RapidAPI-Host": "real-time-web-search.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    response_data = response.json()
    # response_data = join_and_clean_snippets(response_data.text)
    # def display_search_results(json_data):
    #     data = json_data['data']
    #     for item in data:
    #         st.sidebar.markdown(f"### [{item['title']}]({item['url']})")
    #         st.sidebar.write(item['snippet'])
    #         st.sidebar.write("---")
    # st.info('Searching the web using: **{web_query}**')
    # display_search_results(response_data)
    # st.session_state.done = True
    urls = []
    for item in response_data['data']:
        urls.append(item['url'])    
    if retrieval == "fulltext" or retrieval == "RAG":
            # st.write(item['url'])
        if scrape_method != "Browserless":
            response_data = scrapeninja(urls, max)
        else:
            response_data = browserless(urls, max)
        # st.info("Web results reviewed.")
        return response_data, urls

    else:
        # st.info("Web snippets reviewed.")
        st.write(f'HERE IS THE SNIPPETS RESPONSE: {response_data}')
        response_data = join_and_clean_snippets(response_data["data"])
        return response_data, urls
    
@st.cache_data
def browserless(url_list, max):
    # st.write(url_list)
    # if max > 5:
    #     max = 5
    response_complete = []
    i = 0
    key = st.secrets["BROWSERLESS_API_KEY"]
    api_url = f'https://chrome.browserless.io/content?token={key}&proxy=residential&proxyCountry=us&proxySticky'

    headers = {
        # 'Cache-Control': 'no-cache',
        'Content-Type': 'application/json'
    }
    while i < max and i < len(url_list):
        url = url_list[i]
        url_parts = urlparse(url)
        # st.write("Scraping...")
        if 'uptodate.com' in url_parts.netloc:
            method = "POST"
            url_parts = url_parts._replace(path=url_parts.path + '/print')
            url = urlunparse(url_parts)
            # st.write(f' here is a {url}')
        payload =  {
            "url": url,
            # "rejectResourceTypes": ["image"],
        }
        
        response = requests.post(api_url, headers=headers, json=payload)
        # response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            st.write(f'One of the sites failed to release all content: {response.status_code}')
            # st.write(f'Response text: {response.text}')
            # st.write(f'Response headers: {response.headers}')
        try:
            # st.write(f'Response text: {response.text}')  # Print out the raw response text
            # soup = BeautifulSoup(response.text, 'html.parser')
            # clean_text = soup.get_text(separator=' ')
            # # st.write(clean_text)
            # # st.write("Scraped!")
            response_complete.append(response.text)
        except json.JSONDecodeError:
            st.write("Error decoding JSON")
        i += 1
    full_response_str = ' <END OF SITE> '.join(response_complete)
    full_response = clean_and_split_html(full_response_str)
    # limited_text = limit_tokens(full_response, 12000)
    # st.write(f'Here is the lmited text: {limited_text}')
    return full_response

@st.cache_data
def limit_tokens(text, max_tokens=10000):
    tokens = text.split()  # split the text into tokens (words)
    limited_tokens = tokens[:max_tokens]  # keep the first max_tokens tokens
    limited_text = ' '.join(limited_tokens)  # join the tokens back into a string
    return limited_text

@st.cache_data
def scrapeninja(url_list, max):
    # st.write(url_list)
    if max > 5:
        max = 5
    response_complete = []
    i = 0
    method = "POST"
    key = st.secrets["X-RapidAPI-Key"]
    headers = {
        "content-type": "application/json",
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": "scrapeninja.p.rapidapi.com",
    }
    while i < max and i < len(url_list):
        url = url_list[i]
        url_parts = urlparse(url)
        # st.write("Scraping...")
        if 'uptodate.com' in url_parts.netloc:
            method = "POST"
            url_parts = url_parts._replace(path=url_parts.path + '/print')
            url = urlunparse(url_parts)
            st.write(f' here is a {url}')
        payload =  {
            "url": url,
            "method": "POST",
            "retryNum": 1,
            "geo": "us",
            "js": True,
            "blockImages": False,
            "blockMedia": False,
            "steps": [],
            "extractor": "// define function which accepts body and cheerio as args\nfunction extract(input, cheerio) {\n    // return object with extracted values              \n    let $ = cheerio.load(input);\n  \n    let items = [];\n    $('.titleline').map(function() {\n          \tlet infoTr = $(this).closest('tr').next();\n      \t\tlet commentsLink = infoTr.find('a:contains(comments)');\n            items.push([\n                $(this).text(),\n              \t$('a', this).attr('href'),\n              \tinfoTr.find('.hnuser').text(),\n              \tparseInt(infoTr.find('.score').text()),\n              \tinfoTr.find('.age').attr('title'),\n              \tparseInt(commentsLink.text()),\n              \t'https://news.ycombinator.com/' + commentsLink.attr('href'),\n              \tnew Date()\n            ]);\n        });\n  \n  return { items };\n}"
        }
        
        response = requests.request(method, url, json=payload, headers=headers)
        # response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            st.write(f'The site failed to release all content: {response.status_code}')
            # st.write(f'Response text: {response.text}')
            # st.write(f'Response headers: {response.headers}')
        try:
            # st.write(f'Response text: {response.text}')  # Print out the raw response text
            soup = BeautifulSoup(response.text, 'html.parser')
            clean_text = soup.get_text(separator=' ')
            # st.write(clean_text)
            # st.write("Scraped!")
            response_complete.append(clean_text)
        except json.JSONDecodeError:
            st.write("Error decoding JSON")
        i += 1
    full_response = ' '.join(response_complete)
    # limited_text = limit_tokens(full_response, 12000)
    # st.write(f'Here is the lmited text: {limited_text}')
    return full_response
    # st.write(full_response)    
    # Join all the scraped text into a single string
    # return full_response

@st.cache_data
def reconcile(question, old, new, web_content):
    # Send a message to the model asking it to summarize the text
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": reconcile_prompt},
            {"role": "user", "content": f' User question: {question} \n\n, prior answer 1" {old} \n\n, prior answer 2: {new} \n\n, web evidence: {web_content} \n\n'}
        ]
    )
    # Return the content of the model's response
    return response.choices[0].message.content



@st.cache_data
def answer_using_prefix(prefix, sample_question, sample_answer, my_ask, temperature, history_context, model, print = False):

    if model == "openai/gpt-3.5-turbo":
        model = "gpt-3.5-turbo"
    if model == "openai/gpt-3.5-turbo-16k":
        model = "gpt-3.5-turbo-16k"
    if model == "openai/gpt-4":
        model = "gpt-4"
    if history_context == None:
        history_context = ""
    messages = [{'role': 'system', 'content': prefix},
            {'role': 'user', 'content': sample_question},
            {'role': 'assistant', 'content': sample_answer},
            {'role': 'user', 'content': history_context + my_ask},]
    if model == "gpt-4" or model == "gpt-3.5-turbo" or model == "gpt-3.5-turbo-16k" or model == "gpt-4-1106-preview":
        openai.api_base = "https://api.openai.com/v1/"
        openai.api_key = st.secrets['OPENAI_API_KEY']
        response = client.chat.completions.create(
            model = model,
            messages = messages,
            temperature = temperature,
            max_tokens = 500,
            stream = False,   
        )
        response= response.choices[0].message.content
        # response = response['choices'][0]['message']["content"]
    else:      
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",

            # model = model,
            # messages = messages,
            headers={"Authorization": "Bearer " + st.secrets["OPENROUTER_API_KEY"], # To identify your app
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://fsm-gpt-med-ed.streamlit.app", # To identify your app
                    "X-Title": "GPT and Med Ed",
                },
            data=json.dumps({
                "model": model, # Optional
                "messages": messages, # Optional
            })
            )
        response = response.json()
        response = response['choices'][0]['message']["content"]
    return response # Change how you access the message content

def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please contact David Liebovitz, MD if you need an updated password for access.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True

if 'user_question' not in st.session_state:
    st.session_state['user_question'] = ''
    
if 'model1_response' not in st.session_state:
    st.session_state['model1_response'] = ''
    
if 'model2_response' not in st.session_state:
    st.session_state['model2_response'] = ''
    
if 'final_response' not in st.session_state:
    st.session_state['final_response'] = ''
    
if 'web_response' not in st.session_state:
    st.session_state['web_response'] = []
    
if 'ebm' not in st.session_state:
    st.session_state.ebm = ''
    
if 'thread' not in st.session_state:
    st.session_state.thread =[]
    
if 'domain_list' not in st.session_state:
    st.session_state.domain_list = domain_list
    

st.set_page_config(page_title='My AI Team', layout = 'centered', page_icon = ':stethoscope:', initial_sidebar_state = 'auto')
st.title("My AI Team")
with st.expander("Please read before using"):
    st.write("This app is a demonstration of consensus approaches to answering clinical questions using AI. It is not intended for clinical use.")
    st.write("Author: David Liebovitz, MD")



if check_password():




    st.session_state['user_question'] = st.text_input("Enter your question for your AI team here:", st.session_state['user_question'])
    use_internet = st.checkbox("Add Internet Resources?")
    if use_internet:
        
        search_method = st.radio("Web search method:", ("Web snippets from up to 10 webpages", "RAG (Retrieval-Augmented Generation) processing full-text from up to 5 webpages"))

        if search_method == "RAG (Retrieval-Augmented Generation) processing full-text from up to 5 webpages":
            use_rag = True
            max = 5
        if search_method == "Web snippets from up to 10 webpages":
            use_snippets = True
            max = 10
        add_domains = st.checkbox("Add additional domains to search?")
        if add_domains:
            domain_to_add = st.text_input("Enter additional domains to the list of options (e.g. www.cdc.gov OR www.nih.gov):",)
            if st.button("Add domain"):
                st.session_state.domain_list.insert(0, domain_to_add)
        with st.expander("Click to View Domains:", expanded=False):
            domains_only = st.multiselect("Click after the last red one to see other options!", st.session_state.domain_list, default=default_domain_list)
        domains = ' OR '.join(['site:' + domain for domain in domains_only])
        # st.write(domains)
        
        # with st.expander("Domains used with web search:"):
            
        #     for site in domain_list:
        #         st.write(site)

        # max = 4
        # if use_rag:
        #     max = 9
        
    st.info("Please select the models you would like to use to answer your question. The first two models will be used to generate answers, and the third model will be used to reconcile the two answers and any web search results.")
    st.warning("Please note this is a demo of late-breaking methods and there may be errors. Validate all answers independently before *thinking* of leveraging answers beyond just AI exploration.")
    col1, col2 = st.columns(2)

    with col1:
        model1 = st.selectbox("Model 1 Options", ("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-16k",  "openai/gpt-4", "openai/gpt-4-1106-preview", "anthropic/claude-instant-v1", "google/palm-2-chat-bison", "phind/phind-codellama-34b", "meta-llama/llama-2-70b-chat", "gryphe/mythomax-L2-13b", "nousresearch/nous-hermes-llama2-13b"), index=1)
        model2 = st.selectbox("Model 2 Options", ("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-16k",  "openai/gpt-4", "openai/gpt-4-1106-preview", "anthropic/claude-instant-v1", "google/palm-2-chat-bison", "meta-llama/codellama-34b-instruct", "meta-llama/llama-2-70b-chat", "gryphe/mythomax-L2-13b", "nousresearch/nous-hermes-llama2-13b"), index=5)
        model3 = st.selectbox("Model 3 Options", ("openai/gpt-3.5-turbo", "openai/gpt-3.5-turbo-16k",  "openai/gpt-4", "openai/gpt-4-1106-preview", "anthropic/claude-instant-v1", "google/palm-2-chat-bison", "meta-llama/codellama-34b-instruct", "meta-llama/llama-2-70b-chat", "gryphe/mythomax-L2-13b", "nousresearch/nous-hermes-llama2-13b"), index=3)
        if use_rag:
            model4 = st.selectbox("RAG Model Options: Only OpenAI models (ADA for embeddings)", ("gpt-3.5-turbo", "gpt-3.5-turbo-16k",  "gpt-4", "gpt-4-1106-preview"), index=3)
    # model1 = "gpt-3.5-turbo"
    # model2 = "gpt-3.5-turbo-16k"
    # # model3 = "gpt-4-1106-preview"
    # model3 = "undi95/toppy-m-7b"

    begin = st.button("Ask")

    if begin:

        # """
        # Main function to execute API calls concurrently.
        # """
        # Define the arguments for each function call
        args1 = (prefix, '', '', st.session_state.user_question, 0.4, '', model1, False)
        args2 = (prefix, '', '', st.session_state.user_question, 0.4, '', model2, False)
        if use_internet:
            args3 = (st.session_state.user_question, max)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future1 = executor.submit(answer_using_prefix, *args1)
            future2 = executor.submit(answer_using_prefix, *args2)
            if use_internet:
                future3 = executor.submit(websearch_snippets, *args3)
     

        
            with st.spinner('Waiting for models to respond...'):    
            
                try:
                    model1_response = future1.result()
                    st.session_state.model1_response = f'{model1} response:\n\n{model1_response}'
                    time1 = datetime.datetime.now()  # capture current time when process 1 finishes
                except:
                    st.error("Model 1 failed to respond; consider changing.")
                    model1_response = "Model 1 failed to respond."
                
                try:
                    model2_response = future2.result()
                    st.session_state.model2_response = f'{model2} response:\n\n{model2_response}'
                    time2 = datetime.datetime.now()  # capture current time when process 2 finishes
                except:
                    st.error("Model 2 failed to respond; consider changing.")
                    model2_response = "Model 2 failed to respond."
                if use_internet:
                    try:
                        web_response, urls = future3.result()
                        st.session_state.web_response = web_response
                        time3 = datetime.datetime.now()  # capture current time when process 3 finishes
                    except:
                        st.error("Web search failed to respond; try again or uncheck internet searching.")
                        web_response = "Web search failed to respond."
    

        with col2:
            with st.expander(f'Model 1 Response'):
                st.write(st.session_state.model1_response)
                

            with st.expander(f"Model 2 Response"):
                st.write(st.session_state.model2_response)
                
            if use_snippets:
                with st.expander(f"Web Snippets:"):
                    for snip in st.session_state.web_response:
                        st.markdown(snip)

            elif use_rag: 
                with st.spinner('Obtaining fulltext from web search results...'):
                    web_scrape_response = scrapeninja(urls, max) 
                    rag = prepare_rag(web_scrape_response, model4)                
                with st.spinner('Searching the vector database to assemble your answer...'):    
                    evidence_response = rag(st.session_state.user_question)
                    evidence_response = evidence_response["result"]
                    web_response = f'Distilled RAG content from evidence:\n\n{evidence_response}'
                    st.session_state.ebm = web_response

                
            else:
                web_response = "No web search results included."

            if st.session_state.ebm is not '':
                with st.expander('Content retrieved from the RAG model:'):
                    st.markdown(st.session_state.ebm)   
                       
                

        final_answer = reconcile(st.session_state.user_question, model1_response, model2_response, web_response)
        st.session_state.final_response = f'{st.session_state.user_question}\n\nFinal Response from {model3}\n\n{final_answer}'
        st.write(final_answer)
    
    with st.sidebar:
        st.header('Download and View Last Reponses')
        st.write('Updating parameters on the main page resets outputs, so view prior results here.')
        if st.session_state.model1_response is not '':
            with st.expander(f'Model 1 Response'):
                st.write(st.session_state.model1_response)
                st.download_button('Download Model1 Summary', st.session_state.model1_response, f'model1.txt', 'text/txt')
        if st.session_state.model2_response is not '':        
            with st.expander(f"Model 2 Response"):
                st.write(st.session_state.model2_response)
                st.download_button('Download Model2 Summary', st.session_state.model2_response, f'model2.txt', 'text/txt')
        if st.session_state.ebm is not '':
            with st.expander('Content retrieved from the RAG model'):
                st.markdown(st.session_state.ebm)  
                st.download_button('Download RAG Evidence Summary', st.session_state.ebm, f'rag.txt', 'text/txt')
        if len(st.session_state.web_response) is not 0:
            if use_snippets:
                with st.expander(f"Web Search Content:"):                
                    st.markdown("Web Snippets:")
                    for snip in st.session_state.web_response:                    
                        st.markdown(snip) 
                    st.download_button('Download Web Snippets', str(st.session_state.web_response), f'web_snips.txt', 'text/txt')
        if st.session_state.final_response is not '':        
            with st.expander(f"Current Consensus Response"):
                st.write(st.session_state.final_response)
                if len(st.session_state.thread) == 0 or st.session_state.thread[-1] != st.session_state.final_response:
                    st.session_state.thread.append(st.session_state.final_response)
                st.download_button('Download Final Response', st.session_state.final_response, f'final_response.txt', 'text/txt')

        st.write("_______")
        if st.session_state.thread is not []:        
            with st.expander(f"Saved Record of Consensus Responses"):
                convo_str = ''
                convo_str = "\n\n________\n\n________\n\n".join(st.session_state.thread)
                st.write(convo_str)
                st.download_button('Download Conversation Record', convo_str, f'convo.txt', 'text/txt')
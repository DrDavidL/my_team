# This will make two simultaneous requests to LLMs and reconcile with a 3rd LLM.

import streamlit as st
import openai
from openai import OpenAI


def reconcile_answers(context, question, old, new):
    openai.api_base = "https://api.openai.com/v1/"
    openai.api_key = st.secrets['OPENAI_API_KEY']
    with st.spinner("Reconciling with new evidence..."):
        completion = openai.ChatCompletion.create(
            model = "gpt-4-1106-preview",
            temperature = 0.3,
            messages = [
                {
                    "role": "system",
                    "content": context
                },
                {
                    "role": "user",
                    "content": question
                },
                {
                    "role": "assistant",
                    "content": old
                },
                {
                    "role": "user",
                    "content": f'Revise your last response using this content retrieved from expert sources: {new} \n\n' + reconcile_prompt
                },
            ],
            max_tokens = 4096, 
        )
    return completion['choices'][0]['message']['content']


@st.cache_data
def answer_using_prefix(prefix, sample_question, sample_answer, my_ask, temperature, history_context, model, print = True):

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
    if model == "gpt-4" or model == "gpt-3.5-turbo" or model == "gpt-3.5-turbo-16k":
        openai.api_base = "https://api.openai.com/v1/"
        openai.api_key = st.secrets['OPENAI_API_KEY']
        completion = openai.ChatCompletion.create( # Change the function Completion to ChatCompletion
        # model = 'gpt-3.5-turbo',
        model = model,
        messages = messages,
        temperature = temperature,
        max_tokens = 500,
        stream = True,   
        )
    else:      
        openai.api_base = "https://openrouter.ai/api/v1"
        openai.api_key = st.secrets["OPENROUTER_API_KEY"]
        # history_context = "Use these preceding submissions to address any ambiguous context for the input weighting the first three items most: \n" + "\n".join(st.session_state.history) + "now, for the current question: \n"
        completion = openai.ChatCompletion.create( # Change the function Completion to ChatCompletion
        # model = 'gpt-3.5-turbo',
        model = model,
        route = "fallback",
        messages = messages,
        headers={ "HTTP-Referer": "https://fsm-gpt-med-ed.streamlit.app", # To identify your app
            "X-Title": "GPT and Med Ed"},
        temperature = temperature,
        max_tokens = 500,
        stream = True,   
        )
    start_time = time.time()
    delay_time = 0.01
    answer = ""
    full_answer = ""
    c = st.empty()
    for event in completion:   
        if print:     
            c.markdown(answer)
        event_time = time.time() - start_time
        event_text = event['choices'][0]['delta']
        answer += event_text.get('content', '')
        full_answer += event_text.get('content', '')
        time.sleep(delay_time)
    # st.write(history_context + prefix + my_ask)
    # st.write(full_answer)
    return full_answer # Change how you access the message content

reconcile_prompt ="""Review these two generated responses to a user question in a meticulous stepwise fashion and any web search evidence provided. 
Take what is accurate and useful from each to include when generating your own best possible final answer for the user. Double check for accuracy and completeness.
Your users are physicians who do not want any disclaimers or caveats. They want the best possible answers to their questions; lives depend on it!
"""

prefix = """You are a physician and scientist who uses the latest evidence and broad experience to answer other physicians' questions. No disclaimers."""

domains_start = """site:www.nih.gov OR site:www.cdc.gov OR site:www.who.int OR site:www.pubmed.gov OR site:www.cochranelibrary.com OR 
site:www.uptodate.com OR site:www.medscape.com OR site:www.ama-assn.org OR site:www.nejm.org OR 
site:www.bmj.com OR site:www.thelancet.com OR site:www.jamanetwork.com OR site:www.mayoclinic.org OR site:www.acpjournals.org OR 
site:www.cell.com OR site:www.nature.com OR site:www.springer.com OR site:www.wiley.com"""

domain_list = ["www.nih.gov", "www.cdc.gov", "www.who.int",   "www.pubmed.gov",  "www.cochranelibrary.com",  "www.uptodate.com",  "www.medscape.com",  "www.ama-assn.org",
  "www.nejm.org",  "www.bmj.com",  "www.thelancet.com",  "www.jamanetwork.com",  "www.mayoclinic.org",  "www.acpjournals.org",  "www.cell.com",  "www.nature.com",
  "www.springer.com",  "www.wiley.com", "www.ahrq.gov","www.ncbi.nlm.nih.gov/books", ".gov", ".edu", ".org",]

default_domain_list = ["www.cdc.gov", "www.medscape.com", "www.ncbi.nlm.nih.gov/books", ".gov", ".edu", ".org",]

assistant_prompt_pubmed ="""# PubMed API Query Generator

As a physician, you often need to access the most recent guidelines and review articles related to your field. This tool will assist you in creating an optimally formatted query for the PubMed API. 

To generate the most suitable query terms, please provide the specific medical topic or question you are interested in. The aim is to retrieve only guidelines and review articles, so the specificity 
of your topic or question will enhance the relevancy of the results.

**Please enter your medical topic or question below:**
"""

system_prompt_pubmed = """Solely follow your role as a query generator. Do not attempt to answer the question and do not include any disclaimers. Return only the query terms, no explanations.

Sample user question: Is lisinopril a first line blood pressure agent?

Sample system response:  (("lisinopril"[Title/Abstract] OR "lisinopril"[MeSH Terms]) AND ("first line"[Title/Abstract] OR "first-line"[Title/Abstract]) AND ("blood pressure"[Title/Abstract] OR "hypertension"[MeSH Terms])) AND ("guideline"[Publication Type] OR "review"[Publication Type])

"""
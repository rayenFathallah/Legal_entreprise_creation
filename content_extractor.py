import google.generativeai as genai
from langchain_community.document_loaders import PyPDFLoader
import json
import re
import os
import pdfplumber

# Configure Gemini with your API key
genai.configure(api_key="api-key-here")

# Initialize Gemini model
model = genai.GenerativeModel('models/gemini-2.0-flash')

# Function to read and combine PDF pages into a single string
def read_pdf(file_path):
    loader = PyPDFLoader(file_path)
    pages = loader.load_and_split()
    full_text = "\n".join([page.page_content for page in pages])
    return full_text

def read_pdf_arabic(file_path):
    with pdfplumber.open(file_path) as pdf:
        full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])
    return full_text

# Function to ask Gemini to extract specific fields in structured JSON format
def extract_key_fields(pdf_text):
    prompt = f"""
    Tu es un assistant intelligent qui lit un formulaire administratif.

    Voici le contenu extrait du PDF :

    --- Début du texte ---
    {pdf_text}
    --- Fin du texte ---

    Ta tâche est d’extraire les informations suivantes en respectant **strictement** le format JSON ci-dessous. Chaque champ doit être une **clé** et sa valeur doit être **une liste (array)** contenant les éléments extraits.

    Format JSON attendu :
    {{
    "documents_demandes": [...],
    "delais": [...],
    "redevances_a_acquitter": [...],
    "observations": [...]
    }}

    Si un champ est vide, retourne une liste vide. Ne commente rien, retourne uniquement le JSON.
        """
    
    response = model.generate_content(prompt)
    raw_output = response.text

    # Extract JSON content between the first '{' and the last '}'
    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print("❌ Erreur de parsing JSON :", e)
            print("⛔ JSON extrait brut :", json_str)
            return None
    else:
        print("⚠️ Aucun bloc JSON trouvé dans la réponse.")
        print("🔍 Réponse brute :", raw_output)
        return None

def extract_key_fields_arabic(pdf_text):
    prompt = f"""
    أنت مساعد ذكي يقرأ نموذجًا إداريًا مكتوبًا باللغة العربية.

    فيما يلي النص المستخرج من ملف PDF:

    --- بداية النص ---
    {pdf_text}
    --- نهاية النص ---

    مهمتك هي استخراج المعلومات التالية، ولكن يجب أن تستخدم مفاتيح JSON التالية باللغة الفرنسية. كل قيمة يجب أن تكون قائمة (array).

    المفاتيح المطلوبة في ملف JSON الناتج:
    {{
    "documents_demandes": [...],
    "delais": [...],
    "redevances_a_acquitter": [...],
    "observations": [...]
    }}

    إذا لم يكن هناك محتوى لأحد الحقول، فأرجع قائمة فارغة فقط. لا تضف أي تعليق، فقط أرجع JSON كما هو.
    """

    response = model.generate_content(prompt)
    raw_output = response.text

    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print("❌ Erreur de parsing JSON :", e)
            print("⛔ JSON extrait brut :", json_str)
            return None
    else:
        print("⚠️ Aucun bloc JSON trouvé dans la réponse.")
        print("🔍 Réponse brute :", raw_output)
        return None

# Process all files in the 'forms' directory that end with 'Fr.pdf'
import time

def preprocess_pdf_forms(language):
    forms_folder = "forms"
    for file_name in os.listdir(forms_folder):
        if file_name.endswith(f"{language}.pdf"):
            file_path = os.path.join(forms_folder, file_name)
            print(f"\n📄 Traitement du fichier : {file_name}")
            
            max_retries = 3
            attempt = 0
            success = False

            while attempt < max_retries and not success:
                try:
                    pdf_text = read_pdf(file_path)
                    extracted_info = extract_key_fields(pdf_text) if language == "Fr" else extract_key_fields_arabic(pdf_text)

                    if extracted_info:
                        json_file_name = file_name.replace(".pdf", ".json")
                        json_path = os.path.join(forms_folder, json_file_name)
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(extracted_info, f, indent=2, ensure_ascii=False)
                        print(f"✅ JSON sauvegardé : {json_file_name}")
                    else:
                        print(f"⚠️ Aucune information extraite pour : {file_name}")
                    success = True  # No exception, so we're done

                except Exception as e:
                    attempt += 1
                    print(f"❌ Erreur (tentative {attempt}/3) lors du traitement de {file_name} : {e}")
                    if attempt < max_retries:
                        print("⏳ Nouvelle tentative dans 10 secondes...")
                        time.sleep(10)
                    else:
                        print("🚫 Échec après 3 tentatives. Passage au fichier suivant.")

def check_json_files(language):
    
    forms_folder = "forms"
    missing_json = []
    
    # Get all Fr.pdf files
    pdf_files = [f for f in os.listdir(forms_folder) if f.endswith(f"{language}.pdf")]
    
    for pdf_file in pdf_files:
        # Get the expected JSON filename
        json_file = pdf_file.replace(".pdf", ".json")
        json_path = os.path.join(forms_folder, json_file)
        
        # Check if JSON file exists
        if not os.path.exists(json_path):
            missing_json.append(pdf_file)
    
    # Print results
    if missing_json:
        print("❌ Missing JSON files for the following PDFs:")
        for pdf in missing_json:
            print(f"  - {pdf}")
    else:
        print(f"✅ All {language}.pdf files have corresponding JSON files.")

check_json_files("Fr")

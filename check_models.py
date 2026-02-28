# check_models.py
import os
import google.generativeai as genai

print("--- Checking Available AI Models ---")

try:
    # 1. Get the API key from the environment variable
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("\nERROR: GOOGLE_API_KEY is not set.")
        print("Please set the environment variable before running this script.")
        exit()

    genai.configure(api_key=api_key)

    # 2. List all available models and find the ones that can generate content
    print("\nFound the following models that support content generation:")
    print("---------------------------------------------------------")

    found_model = False
    for model in genai.list_models():
        if 'generateContent' in model.supported_generation_methods:
            print(model.name)
            found_model = True

    if not found_model:
        print("No suitable models were found for this API key.")
    else:
        print("---------------------------------------------------------")
        print("\nSUCCESS: Please copy one of the model names from the list above.")

except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")
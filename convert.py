import json
import pandas as pd

def json_to_dataframe(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Flatten the JSON data – this will create separate columns for nested keys
    df = pd.json_normalize(data)
    return df

if __name__ == "__main__":
    file_path = r".\gtmf\gtmf_example.json"
    df = json_to_dataframe(file_path)
    print(df.head())
    # Extract the DataFrame to an Excel file with a proper Windows path
    df.to_excel(r".\gtmf\gtmf_example.xlsx", index=False)
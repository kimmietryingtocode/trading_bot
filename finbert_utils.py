from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from typing import Tuple

tokenizer = AutoTokenizer.from_pretained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretained("ProsusAI/finbert")
labels = ["positive", "negative", "neutral"]

def estimate_sentiment(news):
    if news:
        tokens = tokenizer(news, return_tensors="pt", padding=True)
        result = model(tokens["input_ids"], attention_mask=tokens["attention_mask"])["logits"]

        result = torch.nn.functional.softmax(torch.sum(result,0),dim=-1)
        probability = result[torch.argmax(result)]
        sentiment = labels[torch.argmax(result)]
        return probability, sentiment
    else:
        return 0, labels[-1]
    

if __name__ == "__main__":
    tensor, sentiment = estimate_sentiment(['markets responded negatively to the news!','traders were displeased!'])
    print(tensor, sentiment)
    print(torch.cuda.is_available())


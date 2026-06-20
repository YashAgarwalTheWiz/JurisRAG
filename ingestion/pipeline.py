import time
from datasets import load_dataset
from ingestion.extract import extract
from ingestion.neo4j_loader import load_case
from ingestion.qdrant_loader import load_to_qdrant

CHECKPOINT_FILE = 'processed_ids.txt'
DATASET_LIMIT = 360

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    except FileNotFoundError:
        return set()

def save_checkpoint(case_id):
    with open(CHECKPOINT_FILE, 'a') as f:
        f.write(case_id + '\n')

def run():
    dataset = load_dataset("Exploration-Lab/IL-TUR", "cjpe")['single_train']
    processed = load_checkpoint()
    limit = min(DATASET_LIMIT, len(dataset))

    for case in dataset.select(range(limit)):
        case_id = case['id']
        text = case['text']
        label = case['label']

        if case_id in processed:
            print(f'skipping {case_id} - already processed')
            continue

        try:
            extraction = extract(text)
            load_case(case_id, text, label, extraction)
            load_to_qdrant(case_id, text)
            save_checkpoint(case_id)
            print(f'processed {case_id}')
            time.sleep(2)
        except Exception as e:
            print(f'failed {case_id}: {e}')
            continue

if __name__ == '__main__':
    run()
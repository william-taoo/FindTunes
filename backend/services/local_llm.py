"""Local Transformers generation. No hosted inference or provider credentials."""
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

DEFAULT_MODEL = 'Qwen/Qwen3-0.6B'
MODEL_CACHE = Path(__file__).resolve().parents[1] / '.model-cache' / 'huggingface'
_lock = Lock()


def model_name():
    return os.getenv('LOCAL_LLM_MODEL', DEFAULT_MODEL)


def model_directory():
    return MODEL_CACHE / model_name().replace('/', '--')


@lru_cache(maxsize=1)
def load_model():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Download explicitly with scripts/download_local_model.py first.
    options = {'local_files_only': True,
               'trust_remote_code': False, 'token': False}
    directory = model_directory()
    if not (directory / 'config.json').is_file():
        raise ValueError('Download the local model with scripts/download_local_model.py first')
    tokenizer = AutoTokenizer.from_pretrained(str(directory), **options)
    device = os.getenv('LOCAL_LLM_DEVICE', 'cpu')
    if device not in ('cpu', 'cuda'):
        raise ValueError('LOCAL_LLM_DEVICE must be cpu or cuda')
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA was requested but is unavailable')
    model = AutoModelForCausalLM.from_pretrained(
        str(directory), dtype=torch.float16 if device == 'cuda' else torch.float32,
        **options).to(device)
    model.eval()
    return tokenizer, model


def generate_local(prompt):
    import torch

    # Serialize loading and generation to bound RAM usage across requests.
    with _lock:
        tokenizer, model = load_model()
        roles = {'system': 'system', 'human': 'user', 'ai': 'assistant'}
        messages = [{'role': roles[message.type], 'content': message.content}
                    for message in prompt.to_messages()]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        inputs = tokenizer(text, return_tensors='pt', truncation=False).to(model.device)
        input_length = inputs['input_ids'].shape[-1]
        if input_length > 4096:
            raise ValueError('Lyric comparison exceeds the local input token budget')
        with torch.inference_mode():
            output = model.generate(
                **inputs, max_new_tokens=512, max_time=45,
                do_sample=True, temperature=0.7, top_p=0.8, top_k=20,
                repetition_penalty=1.1, pad_token_id=tokenizer.eos_token_id)
        return tokenizer.decode(output[0][input_length:], skip_special_tokens=True).strip()

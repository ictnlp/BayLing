"""
Apply the delta weights on top of a base model.

Usage:
python apply_delta.py --base-model-path ${PATH_TO_LLAMA} \
		--target-model-path ${PATH_TO_BAYLING} \
		--delta-path ${PATH_TO_DOWNLOAD_BAYLING_DIFF}
"""
import argparse
import gc
import glob
import json
import os
import shutil
import tempfile

from huggingface_hub import snapshot_download
import torch
from torch import nn
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM, AutoConfig


def apply_delta(base_model_path, target_model_path, delta_path):
    print(f"Loading the delta weights from {delta_path}")
    delta_tokenizer = AutoTokenizer.from_pretrained(delta_path, use_fast=False)
    delta = AutoModelForCausalLM.from_pretrained(
        delta_path, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )

    print(f"Loading the base model from {base_model_path}")
    base = AutoModelForCausalLM.from_pretrained(
        base_model_path, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )

    print("Applying the delta")
    for name, param in tqdm(delta.state_dict().items(), desc="Applying delta"):
        assert name in base.state_dict()
        param.data += base.state_dict()[name]

    print(f"Saving the target model to {target_model_path}")
    delta.save_pretrained(target_model_path)
    delta_tokenizer.save_pretrained(target_model_path)


def make_diff(base_model_path, target_model_path, delta_path):
    print(f"Loading the target weights from {target_model_path}")
    target_tokenizer = AutoTokenizer.from_pretrained(target_model_path, use_fast=False)
    target = AutoModelForCausalLM.from_pretrained(
        target_model_path, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )

    print(f"Loading the base model from {base_model_path}")
    base = AutoModelForCausalLM.from_pretrained(
        base_model_path, torch_dtype=torch.float16, low_cpu_mem_usage=True
    )

    print("Making the diff param.")
    for name, param in tqdm(target.state_dict().items(), desc="Making diff"):
        assert name in base.state_dict()
        param.data -= base.state_dict()[name]

    print(f"Saving the diff model to {delta_path}")
    target.save_pretrained(delta_path)
    target_tokenizer.save_pretrained(delta_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model-path", type=str, required=True)
    parser.add_argument("--target-model-path", type=str, required=True)
    parser.add_argument("--delta-path", type=str, required=True)
    parser.add_argument(
        "--make-diff",
        action="store_true",
        help="Make diff",
    )
    args = parser.parse_args()
    if args.make_diff:
        make_diff(args.base_model_path, args.target_model_path, args.delta_path)
    else:
        apply_delta(args.base_model_path, args.target_model_path, args.delta_path)

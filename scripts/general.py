"""
generat the responses on BayLing-80 test set.

Usage:
python ./scripts/general.py --model-path ${PATH_TO_BAYLING} --load-8bit \
    --input-file ${path_to_BayLing-80.multiturn.zh.jsonl$ --output-file ${path_to_save_response$
"""
import argparse
import json
import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
parent_dir_path = os.path.abspath(os.path.join(dir_path, os.pardir))
sys.path.insert(0, parent_dir_path)

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from bayling.model_adapter import add_model_args
from bayling.model_adapter import load_model, get_conversation_template
import tqdm

try:
    from fastchat.model.chatglm_model import chatglm_generate_stream
except:
    chatglm_generate_stream = None


@torch.inference_mode()
def main(args):
    model, tokenizer = load_model(
        args.model_path,
        args.device,
        args.num_gpus,
        args.max_gpu_memory,
        args.load_8bit,
        args.cpu_offloading,
        debug=args.debug,
    )

    is_chatglm = "chatglm" in str(type(model)).lower()

    with open(args.input_file, "r") as file:
        input_lines = file.readlines()

    conversations = []
    for line in input_lines:
        conversation = json.loads(line)
        conversations.append(conversation)

    with open(args.output_file, "w") as file:
        i = 0
        for conversation in tqdm.tqdm(conversations):
            i += 1
            conv = get_conversation_template(args.model_path)

            conversation["response"] = []
            for inst in conversation["text"]:
                inst = inst.strip("\n")
                conv.append_message(conv.roles[0], inst)
                conv.append_message(conv.roles[1], None)

                if is_chatglm:
                    assert chatglm_generate_stream is not None
                    prompt = conv.messages[conv.offset :]
                    gen_params = {
                        "model": args.model_path,
                        "prompt": prompt,
                        "temperature": args.temperature,
                        "repetition_penalty": args.repetition_penalty,
                        "max_new_tokens": args.max_new_tokens,
                        "stop": conv.stop_str,
                        "stop_token_ids": conv.stop_token_ids,
                        "echo": False,
                    }
                    outputs = chatglm_generate_stream(
                        model, tokenizer, gen_params, device=args.device
                    )
                    response = ""
                    for output in outputs:
                        response = output["text"]
                else:
                    prompt = conv.get_prompt()
                    input_ids = tokenizer([prompt]).input_ids

                    output_ids = model.generate(
                        torch.as_tensor(input_ids).cuda(),
                        do_sample=True,
                        temperature=args.temperature,
                        repetition_penalty=args.repetition_penalty,
                        max_new_tokens=args.max_new_tokens,
                    )
                    if model.config.is_encoder_decoder:
                        output_ids = output_ids[0]
                    else:
                        output_ids = output_ids[0][len(input_ids[0]) :]
                    response = tokenizer.decode(
                        output_ids,
                        skip_special_tokens=True,
                        spaces_between_special_tokens=False,
                    )
                conversation["response"].append(response)
                conv.update_last_message(response)
            print(conversation)
            json.dump(conversation, file, ensure_ascii=False)
            file.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_model_args(parser)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--repetition_penalty", type=float, default=1.0)
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--message", type=str, default="Hello! Who are you?")

    parser.add_argument("--input-file", type=str)
    parser.add_argument("--output-file", type=str)
    args = parser.parse_args()

    main(args)

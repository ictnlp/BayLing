"""
generat the translation under user's constraints.

Usage:
python ./scripts/constrained_translate.py --model-path ${PATH_TO_BAYLING} --load-8bit \
    --tgt-lang 'Chinese' --instruction-lang zh \
    --input-file ${path_to_constraints.en-zh.zh.jsonl$ --output-file ${path_to_save_translation$
"""
import argparse
import json
import sys
import os
import json

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

    msg = args.message

    is_chatglm = "chatglm" in str(type(model)).lower()

    with open(args.input_file, "r") as file:
        lines = file.readlines()

    input_lines = []
    for line in lines:
        input_line = json.loads(line)
        input_lines.append(input_line)

    with open(args.output_file, "w") as file:
        for line in tqdm.tqdm(input_lines):
            src = line["src"].strip("\n")
            constraints = ", ".join(line["constraint"])
            if args.instruction_lang == "zh":
                msg = f"提供这句话的{args.tgt_lang}翻译：{src}\n确保包含这些词：{constraints}"
            else:
                # msg = f"Provide the {args.tgt_lang} translation for this sentence, making sure to include {constraints}: {src}"
                msg = f"Provide the {args.tgt_lang} translation for this sentence: {src}\nMake sure to include these words: {constraints}"
            conv = get_conversation_template(args.model_path)
            conv.append_message(conv.roles[0], msg)
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
                translation = ""
                for output in outputs:
                    translation = output["text"]
            else:
                prompt = conv.get_prompt()
                input_ids = tokenizer([prompt]).input_ids

                output_ids = model.generate(
                    torch.as_tensor(input_ids).cuda(),
                    do_sample=False,
                    num_beams=5,
                    temperature=args.temperature,
                    repetition_penalty=args.repetition_penalty,
                    max_new_tokens=args.max_new_tokens,
                )
                if model.config.is_encoder_decoder:
                    output_ids = output_ids[0]
                else:
                    output_ids = output_ids[0][len(input_ids[0]) :]
                translation = tokenizer.decode(
                    output_ids,
                    skip_special_tokens=True,
                    spaces_between_special_tokens=False,
                )

            translation = translation.strip().replace("\n", " ")
            line["hypo"] = translation
            json.dump(line, file, ensure_ascii=False)
            file.write("\n")
            print(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    add_model_args(parser)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--repetition_penalty", type=float, default=1.0)
    parser.add_argument("--max-new-tokens", type=int, default=150)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--message", type=str, default="Hello! Who are you?")

    parser.add_argument("--input-file", type=str)
    parser.add_argument("--output-file", type=str)
    parser.add_argument("--instruction-lang", type=str, default="en")
    parser.add_argument("--tgt-lang", type=str)
    args = parser.parse_args()

    main(args)

# Base
accelerate launch --config_file accel_config.yaml main.py finetune --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_Base --max_length 512 --batch_size 8 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_Base --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_Base --max_length 768 --batch_size 2 --epochs 4 --learning_rate 1e-5 --early_stop 1

# SimOrder
accelerate launch --config_file accel_config.yaml main.py finetune --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_SimOrder --max_length 512 --batch_size 8 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_SimOrder --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_SimOrder --max_length 768 --batch_size 2 --epochs 4 --learning_rate 1e-5 --early_stop 1

# WordLevel
accelerate launch --config_file accel_config.yaml main.py finetune --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_WordLevel --max_length 512 --batch_size 8 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_WordLevel --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_WordLevel --max_length 768 --batch_size 2 --epochs 4 --learning_rate 1e-5 --early_stop 1

# EditSequence
accelerate launch --config_file accel_config.yaml main.py finetune --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_EditSequence --max_length 512 --batch_size 8 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_EditSequence --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
accelerate launch --config_file accel_config.yaml main.py finetune --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_EditSequence --max_length 768 --batch_size 2 --epochs 4 --learning_rate 1e-5 --early_stop 1

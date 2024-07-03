# NoContext
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_NoContext --dataset_dir ./TaRBench/projects --data_encoder NoContext --max_length 512
accelerate launch --config_file accel_config.yaml main.py finetune --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_NoContext --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_NoContext --max_length 512 --beam_size 40 --data_encoder NoContext

# SUTCopy
python sutcopy_baseline.py --dataset_dir ./TaRBench/projects --output_dir ./results/SUTCopy


# CEPROT
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/ceprot/codet5p-770m_SimOrder --dataset_dir /home/ahmad/workspace/tc-repair/repair-collection/data/ceprot --data_encoder SimOrder --max_length 512
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/ceprot/codet5p-770m_SimOrder --max_length 512 --beam_size 40 --data_encoder SimOrder

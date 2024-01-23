# Base
python main.py encode --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_Base --dataset_dir ./TaRBench/projects --data_encoder Base --max_length 512
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_Base --dataset_dir ./TaRBench/projects --data_encoder Base --max_length 512
python main.py encode --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_Base --dataset_dir ./TaRBench/projects --data_encoder Base --max_length 768

# SimOrder
python main.py encode --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_SimOrder --dataset_dir ./TaRBench/projects --data_encoder SimOrder --max_length 512
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_SimOrder --dataset_dir ./TaRBench/projects --data_encoder SimOrder --max_length 512
python main.py encode --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_SimOrder --dataset_dir ./TaRBench/projects --data_encoder SimOrder --max_length 768

# WordLevel
python main.py encode --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_WordLevel --dataset_dir ./TaRBench/projects --data_encoder WordLevel --max_length 512
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_WordLevel --dataset_dir ./TaRBench/projects --data_encoder WordLevel --max_length 512
python main.py encode --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_WordLevel --dataset_dir ./TaRBench/projects --data_encoder WordLevel --max_length 768

# EditSequece
python main.py encode --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_EditSequence --dataset_dir ./TaRBench/projects --data_encoder EditSequence --max_length 512
python main.py encode --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_EditSequence --dataset_dir ./TaRBench/projects --data_encoder EditSequence --max_length 512
python main.py encode --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_EditSequence --dataset_dir ./TaRBench/projects --data_encoder EditSequence --max_length 768
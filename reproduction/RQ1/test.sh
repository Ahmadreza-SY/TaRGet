# Base
python main.py test --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_Base --max_length 512 --beam_size 200 --data_encoder Base
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_Base --max_length 512 --beam_size 40 --data_encoder Base
python main.py test --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_Base --max_length 768 --beam_size 40 --data_encoder Base

# SimOrder
python main.py test --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_SimOrder --max_length 512 --beam_size 200 --data_encoder SimOrder
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_SimOrder --max_length 512 --beam_size 40 --data_encoder SimOrder
python main.py test --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_SimOrder --max_length 768 --beam_size 40 --data_encoder SimOrder

# WordLevel
python main.py test --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_WordLevel --max_length 512 --beam_size 200 --data_encoder WordLevel
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_WordLevel --max_length 512 --beam_size 40 --data_encoder WordLevel
python main.py test --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_WordLevel --max_length 768 --beam_size 40 --data_encoder WordLevel

# EditSequence
python main.py test --model plbart --model_path uclanlp/plbart-base --output_dir ./results/plbart-base_EditSequence --max_length 512 --beam_size 200 --data_encoder EditSequence
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/codet5p-770m_EditSequence --max_length 512 --beam_size 40 --data_encoder EditSequence
python main.py test --model codegen --model_path salesforce/codegen-350M-multi --output_dir ./results/codegen-350M-multi_EditSequence --max_length 768 --beam_size 40 --data_encoder EditSequence

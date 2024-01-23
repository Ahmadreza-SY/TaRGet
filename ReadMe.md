# TaRGet: Automated Test Case Repair Using Large Language Models


## Table of Contents
- [Introduction](#introduction)
- [Dataset Overview](#dataset-overview)
- [Study Replication Instructions](#study-replication-instructions)
- [Data Collection Instructions](#data-collection-instructions)

## Introduction
In this work, we introduce TaRGet and TaRBench, both of which are elaborated on in the subsequent sections.

### TaRGet
Ensuring the quality of software systems through testing is a critical aspect of software development. However, the maintenance of test cases presents significant challenges, both in terms of complexity and cost. The constant need for updates to align with evolving systems under test can result in broken test cases, leading to a deterioration in test suite quality and disruptions in the software development process. To address these challenges, we introduce TaRGet (Test Repair GEneraTor), an approach that leverages pre-trained code language models (CLMs) for automated test case repair. TaRGet treats test repair as a language translation task and employs a two-step process to fine-tune a language model using essential context data that characterizes test breakages.

<!-- ### Publication
TODO: Add once published -->


### TaRBench
TaRBench is a comprehensive benchmark that we developed to evaluate the effectiveness of TaRGet in automated test case repair. The benchmark encompasses 45,373 broken test repairs across 59 open-source projects, providing a diverse and extensive dataset for assessing the capabilities of TaRGet. TaRBench data and detailed information can be accessed at: https://figshare.com/s/77598ce966e625c75f5a


## Study Replication Instructions

We conducted our experiments using Python 3.8. Also, Maven 3.6.3, along with JDK versions 1.8.0_192, 11.0.16_8, or 17.0.2, was utilized for executing test cases. The specific JDK version depended on the compiler version specified in the project's pom.xml file.

To begin, install the required Python packages using the following command:
```bash
pip install -r requirements.txt
```

To run each fine-tuning experiment, three commands should be executed sequentially: `encode`, `finetune`, and `test`. First, the data is encoded, preparing it for the language model. Then, the fine-tuning is executed, and finally, the fine-tuned model is tested against the evaluation set to generate repairs. All three commands share the following arguments:

Argument       | Description
-------------- | ---
`--model`      | The name of the CLM, with possible values being `plbart`, `codegen`, or `codet5p`.
`--model_path` | The path to the CLM, which can be either a Hugging Face model name (e.g., `Salesforce/codet5p-770m`) or a path in the local machine (e.g., `/home/ahmad/CodeT5plus`).
`--output_dir` | The output directory to store both data and results.
`--max_length` | The maximum token length used for encoding inputs and outputs for the CLM; in our experiments, it is consistently set to 512.

**Ensure that all commands are executed within the `fine-tuning` directory for proper functionality.** The details for each command are outlined below.

### The `encode` Command
The `encode` command uses TaRBench or a similar benchmark to create and encode inputs and outputs for a specified language model. The input and output formattings (IOs) are defined in our paper. Upon successful execution, this commands creates multiple files in the specified output directory under the `splits` folder. This files include `train.pkl`, `valid.pkl`, and `test.pkl`, along with their corresponding `.json` formats. The `.pkl` files are Python pickles containing the encoded data, while the `.json` files present the inputs and outputs in text format. This command takes the following arguments:

Argument | Description
--- | ---
`--dataset_dir` | The path to TaRBench or a similar benchmark.
`--data_encoder` | The data encoder type, defining the IO during encoding. Possible values include: `Base`, `SimOrder`, `WordLevel`, `EditSeq`, and `NoContext`. Refer to our paper for detailed definitions.
`--train_size` | The ratio of the training data; Always set to 0.8 in our experiments.
`--train_fraction` | The fraction of training data to use for fine-tuning, with a default value of 1.0. This argument is relevant to addressing specific research questions.
`--mask_projects` | A comma-separated list of project names to exclude from the training data. The default value is `None`. This argument is relevant to addressing specific research questions.

Example of the `encode` command:
```bash
python main.py encode --model codet5p --model_path Salesforce/codet5p-770m --output_dir ./results/codet5p-770m_SimOrder --dataset_dir ./TaRBench/projects --data_encoder SimOrder --max_length 512
```

### The `finetune` Command
The `finetune` command reads the encoded data from the `.pkl` files and performs fine-tuning on the CLM for the test repair task. Upon completion, it stores the best checkpoint of the fine-tuned model in the `checkpoint-best` directory within the specified output directory. This command takes the following arguments:

Argument | Description
--- | ---
`--batch_size` | Batch size for both training and validation.
`--epochs` | The number of epochs for the fine-tuning process.
`--learning_rate` | The value for the learning rate during fine-tuning.
`--early_stop` | The number of epochs to continues training while the validation loss does not show improvement.

Example of the `finetune` command:
```bash
python main.py finetune --model codet5p --model_path Salesforce/codet5p-770m --output_dir ./results/codet5p-770m_SimOrder --max_length 512 --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
```

### The `test` Command
The `test` command loads the best model checkpoint from the fine-tuning process and uses it to generate test repair candidates for the evaluation dataset, including both the test and validation sets. As a result, it saves the predictions in the `test_predictions.json` and `checkpoint-best/valid_predictions.json` files. This command takes the following arguments:

Argument | Description
--- | ---
`--data_encoder` | The data encoder type, defining the IO during encoding. Possible values include: `Base`, `SimOrder`, `WordLevel`, `EditSeq`, and `NoContext`. Refer to our paper for detailed definitions.
`--beam_size` | The number of test repair candidates to generate for each test repair instance, using the beam search strategy.
`--mask_projects` | A comma-separated list of project names to exclude from the evaluation data. The default value is None. This argument is relevant to addressing specific research questions.

Example of the `test` command:
```bash
python main.py test --model codet5p --model_path salesforce/codet5p-770m --output_dir ./results/rqs/codet5p-770m_SimOrder --max_length 512 --beam_size 40 --data_encoder SimOrder
```

TODO: For each RQ, provide general instructions on how to run corresponding experiments.


## Data Collection Instructions
Run this command to build `jparser` (required to run the python scripts):
```bash
mvn clean package assembly:single -f jparser
```

First, run the following command to collect the repository's required raw data from GitHub:
```bash
python -u main.py gh_tags -r <repo> -o <output_path>
```
where the `<repo>` is the repository's (`<username>/<reponame>`, for example: `apache/spark`) and the `<output_path>` points to the path that the data is saved.

Then, the following command processes the raw data and creates the test case repair dataset (use the same `<repo>` and `<output_path>` as the previous command):
```bash
python -u main.py dataset -r <repo> -o <output_path>
```
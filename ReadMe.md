# TaRGet: Automated Test Case Repair Using Language Models

## Table of Contents
- [Introduction](#introduction)
- [Experiment Execution](#experiment-execution)
    - [The `encode` Command](#the-encode-command)
    - [The `finetune` Command](#the-finetune-command)
    - [The `test` Command](#the-test-command)
    - [Study Reproduction](#study-reproduction)
    - [Executing Repair Candidates](#executing-repair-candidates)
- [Test Case Repair Data Collection](#test-case-repair-data-collection)

## Introduction
In this work, we introduce TaRGet and TaRBench, both of which are elaborated on in the subsequent sections.

### TaRGet
Ensuring the quality of software systems through testing is a critical aspect of software development. However, the maintenance of test cases presents significant challenges, both in terms of complexity and cost. The constant need for updates to align with evolving systems under test can result in broken test cases, leading to a reduction in test suite quality and disruptions in the software development process. To address these challenges, we introduce TaRGet (Test Repair GEneraTor), an approach that leverages pre-trained code language models (CLMs) for automated test case repair. TaRGet treats test repair as a language translation task and employs a two-step process to fine-tune a language model using essential context data that characterizes test breakages.

### TaRBench
TaRBench is a comprehensive benchmark that we developed to evaluate the effectiveness of TaRGet in automated test case repair. The benchmark encompasses 45,373 broken test repairs across 59 open-source projects, providing a diverse and extensive dataset for assessing the capabilities of TaRGet. TaRBench plus TaRGet's best results and generations can be accessed at: [![DOI](https://zenodo.org/badge/DOI/10.6084/m9.figshare.25008893.svg)](https://doi.org/10.6084/m9.figshare.25008893)


### Publication
This repository is a supplement to our paper which can be found on [arXiv/2401.06765](https://arxiv.org/abs/2401.06765). Please refer to the paper for details on definitions, experiments, and results. If you find this repository useful, please don't forget to ⭐ it and cite our paper:
```
@article{saboor2024target,
      title={Automated Test Case Repair Using Language Models}, 
      author={Ahmadreza Saboor Yaraghi and Darren Holden and Nafiseh Kahani and Lionel Briand},
      year={2024},
      eprint={2401.06765},
      archivePrefix={arXiv},
      url={https://arxiv.org/abs/2401.06765}, 
}
```


## Experiment Execution
We conducted our experiments using Python 3.8.

Before beginning, it is recommended to create and activate a virtual environment, to avoid conflicts with previously installed Python packages. The following steps are suitable for a Bash terminal, for other types of terminals please refer to the offical documentation: [https://docs.python.org/3/library/venv.html](https://docs.python.org/3/library/venv.html)
```
python -m venv /path/to/new/virtual/environment
source /path/to/new/virtual/environment/bin/activate
```

To begin, install the required Python packages using the following command:
```
pip install -r requirements.txt
```

To run each fine-tuning experiment, three commands should be executed sequentially: `encode`, `finetune`, and `test`. First, the data is encoded, preparing it for the language model. Then, the fine-tuning is executed, and finally, the fine-tuned model is tested against the evaluation set to generate repairs. All three commands share the following arguments:
```console
--model        The name of the CLM, with possible values being 'plbart', 
               'codegen', or 'codet5p'.

--model_path   The path to the CLM, which can be either a Hugging Face model 
               name (e.g., 'Salesforce/codet5p-770m') or a path on the local 
               machine (e.g., '/home/ahmad/CodeT5plus').

--output_dir   The output directory to store both data and results.

--max_length   The maximum token length used for encoding inputs and outputs
               for the CLM.
```

**Ensure that all commands are executed within the [`fine-tuning`](./fine-tuning) directory for proper functionality.** The details for each command are outlined below.

### The `encode` Command
The `encode` command uses TaRBench or a similar benchmark to create and encode inputs and outputs for a specified language model. The input and output formattings (IOs) are defined in our paper. Upon successful execution, this command creates multiple files in the specified output directory under the `splits` folder. These files include `train.pkl`, `valid.pkl`, and `test.pkl`, along with their corresponding `.json` formats. The `.pkl` files are Python pickles containing the encoded data, while the `.json` files present the inputs and outputs in text format. This command takes the following arguments:
```console
--dataset_dir     The path to TaRBench or a similar benchmark.

--data_encoder    The data encoder type, defining the IO during encoding. 
                  Possible values include: 'Base', 'SimOrder', 'WordLevel', 
                  'EditSequence', and 'NoContext'. Refer to our paper for 
                  detailed definitions.

--train_size      The ratio of the training data.

--train_fraction  The fraction of training data to use for fine-tuning, with a 
                  default value of 1.0. This argument is relevant to addressing 
                  specific research questions.

--mask_projects   A comma-separated list of project names to exclude from the 
                  training data. The default value is 'None'. This argument is 
                  relevant to addressing specific research questions.
```

Example of the `encode` command:
```
python main.py encode \
  --model codet5p --model_path Salesforce/codet5p-770m \
  --output_dir ./results/codet5p-770m_SimOrder --dataset_dir ./TaRBench/projects \
  --data_encoder SimOrder --max_length 512
```

### The `finetune` Command
The `finetune` command reads the encoded data from the `.pkl` files and performs fine-tuning on the CLM for the test repair task. Upon completion, it stores the best checkpoint of the fine-tuned model in the `checkpoint-best` directory within the specified output directory. This command takes the following arguments:
```console
--batch_size      Batch size for both training and validation.

--epochs          The number of epochs for the fine-tuning process.

--learning_rate   The value for the learning rate during fine-tuning.

--early_stop      The number of epochs to continue training while the 
                  validation loss does not show improvement.
```

Example of the `finetune` command:
```
python main.py finetune \
  --model codet5p --model_path Salesforce/codet5p-770m \
  --output_dir ./results/codet5p-770m_SimOrder --max_length 512 \
  --batch_size 1 --epochs 4 --learning_rate 1e-5 --early_stop 1
```

### The `test` Command
The `test` command loads the best model checkpoint from the fine-tuning process and uses it to generate test repair candidates for the evaluation dataset, including both the test and validation sets. As a result, it saves the predictions in the `test_predictions.json` and `checkpoint-best/valid_predictions.json` files. This command takes the following arguments:
```console
--data_encoder    The data encoder type, defining the IO during encoding. 
                  Possible values include: 'Base', 'SimOrder', 'WordLevel', 
                  'EditSequence', and 'NoContext'. Refer to our paper for 
                  detailed definitions.

--beam_size       The number of test repair candidates to generate for each test 
                  repair instance, using the beam search strategy.

--mask_projects   A comma-separated list of project names to exclude from the 
                  evaluation data. The default value is 'None'. This argument is 
                  relevant to addressing specific research questions.
```

Example of the `test` command:
```
python main.py test --model codet5p --model_path salesforce/codet5p-770m \
--output_dir ./results/codet5p-770m_SimOrder --max_length 512 \
--beam_size 40 --data_encoder SimOrder
```

### Study Reproduction
To reproduce the results of our research questions (RQs), execute the provided commands located in the scripts within the [`reproduction`](./reproduction) folder. We provide bash scripts for RQ1, RQ3.1, and RQ3.2 containing the `encode`, `finetune`, and `test` commands. However, RQ2.1 and RQ2.2 include analysis of the results, hence no fine-tuning commands are available for them. Further details regarding these RQs can be found in our paper.

It is essential to note that the fine-tuning commands begin with `accelerate`. We used Hugging Face's [Accelerate](https://github.com/huggingface/accelerate) library to perform multi-GPU training, with the configuration specified in the [`accel_config.yaml`](./reproduction/accel_config.yaml) file. Our fine-tuning experiments were conducted using two Nvidia Quadro RTX 6000 GPUs, each equipped with 24GB of GPU memory.

### Executing Repair Candidates
To determine the plausible repair accuracy (PR) in our study, we executed the repair candidates using the [`test_run.py`](./fine-tuning/test_run.py) and [`test_run_stats.py`](./fine-tuning/test_run_stats.py) files. For each test repair instance identified by a unique ID in the `test_predictions.json` file, run the `test_run.py` with the following arguments:
```console
--output-path    Directory where all the outputs are stored.

--repo-path      Repository directory where tests will be executed.

--java-homes     Path to a JSON file containing Java homes for various 
                 Java versions.

--test-index     Index of the row to execute from the test set.

--m2-path        Custom path for Maven local repository.
```

We used Maven 3.6.3, along with JDK versions 1.8.0_192, 11.0.16_8, or 17.0.2 for executing test cases. The specific JDK version depends on the compiler version specified in the project's pom.xml file. Example of the Java homes file:
```json
{
    "8": "/var/lib/.sdkman/candidates/java/8.0.302-open",
    "11": "/var/lib/.sdkman/candidates/java/11.0.12-open",
    "17": "/var/lib/.sdkman/candidates/java/17.0.7-tem",
}
```

Example of running the `test_run.py` file:
```
python test_run.py --test-index 0 \
    --output-path ./results/codet5p-770m_SimOrder \
    --repo-path ./repo/apache/druid --m2-path /home/ahmad/.m2 \
    --java-homes /home/ahmad/java_homes.json
```

Finally, execute the `test_run_stats.py` to aggregate the results from all `test_run.py` executions. The aggregated results will be stored in the `test_verdicts.json` file:
```
python test_run_stats.py --output-path ./results/codet5p-770m_SimOrder
```

## Test Case Repair Data Collection
In this repository, we provide the code used to collect test repairs and create TaRBench, our test case repair benchmark. The relevant code is located in the [`repair-collection`](./repair-collection) folder. Below, we guide you on utilizing this tool to collect test case repair data from open-source Java Maven projects on GitHub.

Our data collection tool includes both Python scripts and Java code. Specifically, we use Python 3.8, Java 11.0.16, and Maven 3.6.3. Before running the main data collection script, run the following command in the `repair-collection` folder to build `jparser`—the essential Java component of our tool:
```
mvn clean package assembly:single -f jparser
```

Once the `jparser.jar` is created, run the [`main.py`](./repair-collection/main.py) command to collect test case repairs using the following arguments:
```console
--repository       Login and name of the GitHub repository seperated by '/'.

--output-path      The directory to save the resulting data.

--java-homes       Path to a JSON file containing Java homes for various 
                   Java versions (similar to test_run.py).

--m2-path          Custom path for maven local repository.
```

Example for collecting data for the `apache/druid` project:
```
python main.py --repository apache/druid \
    --output-path ./benchmark/apache/druid \
    --m2-path /home/ahmad/.m2 \
    --java-homes /home/ahmad/java_homes.json
```
The provided command automatically clones the repository, analyzes the commit history, identifies potential test case repairs, executes test cases to validate the repairs, and mines the changes in the repair commits. For a more in-depth understanding of the data collection procedure, please refer to our paper.

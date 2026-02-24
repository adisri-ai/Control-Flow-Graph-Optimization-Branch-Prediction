# Project Overview  
1. This project aims at optimizing the exectuion sequence for various nodes of a given **Control Flow Graph(CFG)** using **LSTM** deep learning model in order to **minimize clock cycles**.
2. We use personality-based Long Short Term Memory(LSTM) deep learning model for this which is used to identify the patterns in user's multiple codes and classify the user into
   among the defined personality classes of coder.
3. This followed by performing branch prediction on the a given code based on the personality it is classified into. Performing branch prediction helps reducing number of clock cycles needed.
# Tech Stack  
1. **Project Logic-Code** : Python
2. **Web Framework**      : Streamlit
3. **Deep Learning Model Package** : Tensorflow
# Project Phases  
The project will be made with the following phases: 
1. **Training Data Generation** : Since there isn't any readily available data for each of the defined personality classes, we generate randomized code for each personality using python.
                                  Refer to the [Documentation](DATA_GENERATION.md) and [Final Generated Data](data_generation/data.csv)
2. **Model Training**           : Once the training data is generated, we train the LSTM model on our training data.
3. **Frontend**                 : Finally, we create a frontend to take user code as input and return the optimal execution sequence.

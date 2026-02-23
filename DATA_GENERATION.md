# Objective
1. The first step of the project includes generating randomized C++ codes having branches in their Control Flow Graph(CFG) such as loops or conditionals.
# Concerned File  
1. *training.csv*
# Output File 
1. *data.csv*
# Personality based Code Generation
1. There are 4 personality classes taken into consideration for this project:
   1. **Verbose coder**
   2. **Compact coder**
   3. **Experimental coder**
   4. **Structured coder**
2. The file *training.py* consists of the following functions:
    1. *_rand_var()* : Used for generating random indentifiers
    2. *_assign_statement()* : To generate statements involing the assignment(=) operator
    3. *_if_block_chain()* : Generate random if-block chain in the code along with label of True/False value of the conditional
    4. *_for_block()*  : Generation of for-block with a label indicating whether the loop executed
# Defining the 4 programming styles  
1. The types of programming styles to be considered are only listed above.  
    We will now use auxiliary functions defined in the earlier section to generate codes in different patterns for each style.
2. We generate randomized codes for each style differently based on patterns depending on branch structure and values of the branches/labels.
3. The file consists of the following functions to build the Control Flow Graph:
     1. *_generate_personality_code()*  : Used for defining the branch structure of the Control Flow Graph.
     2. *generate_codes()*              : Generate random code samples based on specified conditions.

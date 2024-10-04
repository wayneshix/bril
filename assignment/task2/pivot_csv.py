import pandas as pd

# Read the CSV file
df = pd.read_csv('/Users/way/projects/bril/assignment/task2/task2_result.csv')

# Pivot the DataFrame
pivot_table = df.pivot(index='benchmark', columns='run', values='result')

# Reset index to make 'benchmark' a column
pivot_table.reset_index(inplace=True)

# Replace NaN with empty strings if needed
pivot_table = pivot_table.fillna('')



# Print the pivoted table
pivot_table.to_csv('/Users/way/projects/bril/assignment/task2/task2_result_table.csv')
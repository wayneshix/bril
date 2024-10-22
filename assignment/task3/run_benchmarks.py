import subprocess
import difflib
import glob
import os

import subprocess
import difflib
import glob
import os

def run_loop_optimization_benchmark(benchmark_glob_pattern, loop_optimization_script_path):
    """
    Runs loop optimization on a set of Bril benchmark programs and compares the outputs.

    For each benchmark program:
    - Runs the original program and captures its output.
    - Runs the loop-optimized program and captures its output.
    - Compares the outputs.
    - If outputs differ, provides a detailed side-by-side comparison.

    Args:
        benchmark_glob_pattern: Glob pattern to match Bril benchmark programs.
        loop_optimization_script_path: Path to the loop optimization script.
    """
    # Find all benchmark files matching the glob pattern
    benchmark_paths = glob.glob(benchmark_glob_pattern, recursive=True)
    if not benchmark_paths:
        print(f'No benchmark files found matching pattern: {benchmark_glob_pattern}')
        return

    for benchmark_path in benchmark_paths:
        print(f'\nProcessing {benchmark_path}')
        try:
            # Read the original Bril program
            with open(benchmark_path, 'r', encoding='utf-8') as f:
                bril_program = f.read()
            
            # Convert to JSON
            original_json = subprocess.run(
                ['bril2json'],
                input=bril_program,
                capture_output=True,
                text=True,
                check=True
            )

            # Run the original program with brili
            original_output = subprocess.run(
                ['brili'],
                input=original_json.stdout,
                capture_output=True,
                text=True,
                check=True
            )

            # Run the loop optimization script
            optimized_json = subprocess.run(
                ['python3', loop_optimization_script_path],
                input=original_json.stdout,
                capture_output=True,
                text=True,
                check=True
            )

            # Run the optimized program with brili
            optimized_output = subprocess.run(
                ['brili'],
                input=optimized_json.stdout,
                capture_output=True,
                text=True,
                check=True
            )

            # Compare outputs
            if original_output.stdout == optimized_output.stdout:
                print(f'{benchmark_path}: correct')
            else:
                print(f'{benchmark_path}: incorrect')
                print('Output differences:')
                # Use difflib to produce a side-by-side diff
                original_lines = original_output.stdout.splitlines()
                optimized_lines = optimized_output.stdout.splitlines()
                diff = difflib.unified_diff(
                    original_lines,
                    optimized_lines,
                    fromfile='Original Output',
                    tofile='Optimized Output',
                    lineterm=''
                )
                print('\n'.join(diff))
        except subprocess.CalledProcessError as e:
            print(f'Error processing {benchmark_path}: {e}')
            if e.stdout:
                print('Standard output:')
                print(e.stdout)
            if e.stderr:
                print('Error output:')
                print(e.stderr)
        except Exception as e:
            print(f'Unexpected error processing {benchmark_path}: {e}')



# Example usage
if __name__ == '__main__':
    benchmarks = '/Users/way/projects/bril/benchmarks/**/*.bril'
    loop_optimization_script = '/Users/way/projects/bril/assignment/task3/loop_optimization.py'
    run_loop_optimization_benchmark(benchmarks, loop_optimization_script)
#!/usr/bin/env python3
"""
Performance Benchmarking Script for Streamlit Excel Processing App
"""

import time
import psutil
import pandas as pd
import numpy as np
from functools import wraps
import tracemalloc
import sys
import os

def measure_performance(func):
    """Decorator to measure execution time and memory usage"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Start memory tracking
        tracemalloc.start()
        process = psutil.Process(os.getpid())
        
        # Memory before
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Time measurement
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        # Memory after
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Calculate metrics
        execution_time = end_time - start_time
        memory_used = memory_after - memory_before
        peak_memory = peak / 1024 / 1024  # MB
        
        print(f"\n{'='*60}")
        print(f"PERFORMANCE METRICS: {func.__name__}")
        print(f"{'='*60}")
        print(f"⏱️  Execution Time: {execution_time:.2f} seconds")
        print(f"🧠 Memory Usage: {memory_used:.2f} MB")
        print(f"📊 Peak Memory: {peak_memory:.2f} MB")
        print(f"{'='*60}")
        
        return result, {
            'execution_time': execution_time,
            'memory_used': memory_used,
            'peak_memory': peak_memory
        }
    return wrapper

def create_test_data(num_rows=1000):
    """Create test data similar to the Excel structure"""
    np.random.seed(42)  # Reproducible results
    
    # Create base DataFrame (Planilha1)
    base_data = {
        'Column1': range(num_rows),
        'Data': pd.date_range('2023-01-01', periods=num_rows, freq='D'),
        'Disponível': np.random.choice(['Conta A', 'Conta B', 'Conta C'], num_rows),
        'Categoria': np.random.choice(['Cat1', 'Cat2', 'Cat3'], num_rows),
        'Column5': np.random.randn(num_rows),
        'Descrição': [f'Desc {i}' for i in range(num_rows)],
        'Column7': np.random.randn(num_rows),
        'Column8': np.random.randn(num_rows),
        'Column9': np.random.randn(num_rows),
        'Valor': np.random.uniform(10, 1000, num_rows),
        'Detalhe': [f'Detail {i} - Sample description' for i in range(num_rows)]
    }
    base_df = pd.DataFrame(base_data)
    
    # Create pagina1 DataFrame (Página1)
    pagina1_data = {
        'Column1': range(100),
        'Descriptions': [f'Full Detail {i} - Sample description' for i in range(100)]
    }
    pagina1_df = pd.DataFrame(pagina1_data)
    
    return base_df, pagina1_df

@measure_performance
def benchmark_old_fuzzy_matching(base_df, pagina1_df):
    """Benchmark the old fuzzy matching approach"""
    try:
        from fuzzywuzzy import fuzz
        fuzzy_available = True
    except ImportError:
        fuzzy_available = False
        print("⚠️  FuzzyWuzzy not available, using exact matching")
    
    def find_best_match_old(description, pagina1_descriptions):
        if pd.isna(description):
            return None
        if not fuzzy_available:
            # Fallback to exact matching
            clean_description = description.strip()
            for pagina1_desc in pagina1_descriptions:
                if pd.isna(pagina1_desc):
                    continue
                clean_pagina1_desc = pagina1_desc.split(' - ', 1)[-1].strip() if ' - ' in pagina1_desc else pagina1_desc.strip()
                if clean_description.lower() == clean_pagina1_desc.lower():
                    return pagina1_desc
            return None
        
        # Fuzzy matching
        best_match = None
        highest_score = 0
        clean_description = description.strip()
        for pagina1_desc in pagina1_descriptions:
            if pd.isna(pagina1_desc):
                continue
            clean_pagina1_desc = pagina1_desc.split(' - ', 1)[-1].strip() if ' - ' in pagina1_desc else pagina1_desc.strip()
            score = fuzz.token_sort_ratio(clean_description, clean_pagina1_desc) if len(clean_description) > 20 or ',' in clean_description else fuzz.partial_ratio(clean_description, clean_pagina1_desc)
            threshold = 85 if len(clean_description) < 20 else 75
            if score > highest_score and score >= threshold:
                highest_score = score
                best_match = pagina1_desc
        return best_match
    
    # Process the 'Detalhe' column (old way)
    pagina1_descriptions = pagina1_df.iloc[:, 1]
    updated_descriptions = base_df['Detalhe'].copy()
    
    for i in range(len(base_df)):
        desc = base_df['Detalhe'].iloc[i]
        best_match = find_best_match_old(desc, pagina1_descriptions)
        if best_match:
            updated_descriptions.iloc[i] = best_match
    
    base_df['Detalhe'] = updated_descriptions
    return base_df

@measure_performance
def benchmark_new_fuzzy_matching(base_df, pagina1_df):
    """Benchmark the new optimized fuzzy matching approach"""
    from functools import lru_cache
    
    try:
        from fuzzywuzzy import fuzz
        fuzzy_available = True
    except ImportError:
        fuzzy_available = False
        print("⚠️  FuzzyWuzzy not available, using exact matching")
    
    @lru_cache(maxsize=1000)
    def clean_string(text):
        if pd.isna(text):
            return ""
        return str(text).strip().lower()
    
    def preprocess_descriptions(pagina1_descriptions):
        processed = []
        for desc in pagina1_descriptions:
            if pd.isna(desc):
                processed.append(None)
            else:
                clean_desc = desc.split(' - ', 1)[-1].strip() if ' - ' in desc else desc.strip()
                processed.append((desc, clean_desc.lower()))
        return processed
    
    def vectorized_fuzzy_match(descriptions, pagina1_processed, fuzzy_available=False):
        if not fuzzy_available:
            # Optimized exact matching
            result = []
            desc_lower = [clean_string(desc) for desc in descriptions]
            
            for i, desc in enumerate(desc_lower):
                if not desc:
                    result.append(None)
                    continue
                
                match = None
                for original, clean in pagina1_processed:
                    if original is not None and desc == clean:
                        match = original
                        break
                result.append(match)
            
            return result
        
        # Optimized fuzzy matching
        result = []
        
        for desc in descriptions:
            if pd.isna(desc):
                result.append(None)
                continue
            
            clean_desc = clean_string(desc)
            if not clean_desc:
                result.append(None)
                continue
            
            best_match = None
            highest_score = 0
            
            threshold = 85 if len(clean_desc) < 20 else 75
            
            for original, clean_pagina1 in pagina1_processed:
                if original is None:
                    continue
                
                if len(clean_desc) > 20 or ',' in clean_desc:
                    score = fuzz.token_sort_ratio(clean_desc, clean_pagina1)
                else:
                    score = fuzz.partial_ratio(clean_desc, clean_pagina1)
                
                if score > highest_score and score >= threshold:
                    highest_score = score
                    best_match = original
            
            result.append(best_match)
        
        return result
    
    # Process using new optimized method
    pagina1_descriptions = pagina1_df.iloc[:, 1]
    processed_descriptions = preprocess_descriptions(pagina1_descriptions)
    
    matched_descriptions = vectorized_fuzzy_match(
        base_df['Detalhe'].values, 
        processed_descriptions, 
        fuzzy_available
    )
    
    base_df['Detalhe'] = matched_descriptions
    return base_df

def run_comprehensive_benchmark():
    """Run comprehensive performance benchmarks"""
    print("🚀 Starting Performance Benchmark Suite")
    print("="*60)
    
    # Test different dataset sizes
    test_sizes = [100, 500, 1000, 2500, 5000]
    results = {}
    
    for size in test_sizes:
        print(f"\n📊 Testing with {size} rows...")
        
        # Create test data
        base_df, pagina1_df = create_test_data(size)
        
        # Benchmark old approach
        print(f"\n🔍 Benchmarking OLD approach ({size} rows)...")
        base_df_old = base_df.copy()
        try:
            _, old_metrics = benchmark_old_fuzzy_matching(base_df_old, pagina1_df)
        except Exception as e:
            print(f"❌ Old approach failed: {e}")
            old_metrics = {'execution_time': float('inf'), 'memory_used': float('inf')}
        
        # Benchmark new approach
        print(f"\n🚀 Benchmarking NEW approach ({size} rows)...")
        base_df_new = base_df.copy()
        try:
            _, new_metrics = benchmark_new_fuzzy_matching(base_df_new, pagina1_df)
        except Exception as e:
            print(f"❌ New approach failed: {e}")
            new_metrics = {'execution_time': float('inf'), 'memory_used': float('inf')}
        
        # Calculate improvements
        time_improvement = ((old_metrics['execution_time'] - new_metrics['execution_time']) / old_metrics['execution_time']) * 100
        memory_improvement = ((old_metrics['memory_used'] - new_metrics['memory_used']) / old_metrics['memory_used']) * 100
        
        results[size] = {
            'old_time': old_metrics['execution_time'],
            'new_time': new_metrics['execution_time'],
            'time_improvement': time_improvement,
            'old_memory': old_metrics['memory_used'],
            'new_memory': new_metrics['memory_used'],
            'memory_improvement': memory_improvement
        }
        
        print(f"\n📈 IMPROVEMENT SUMMARY ({size} rows):")
        print(f"⏱️  Time: {time_improvement:.1f}% faster")
        print(f"🧠 Memory: {memory_improvement:.1f}% more efficient")
    
    # Print final summary
    print("\n" + "="*80)
    print("🎯 FINAL BENCHMARK RESULTS")
    print("="*80)
    print(f"{'Rows':<8} {'Old Time':<12} {'New Time':<12} {'Time Improve':<15} {'Memory Improve':<15}")
    print("-"*80)
    
    for size, result in results.items():
        print(f"{size:<8} {result['old_time']:<12.2f} {result['new_time']:<12.2f} "
              f"{result['time_improvement']:<15.1f}% {result['memory_improvement']:<15.1f}%")
    
    # Calculate average improvements
    avg_time_improvement = sum(r['time_improvement'] for r in results.values()) / len(results)
    avg_memory_improvement = sum(r['memory_improvement'] for r in results.values()) / len(results)
    
    print("\n🏆 AVERAGE IMPROVEMENTS:")
    print(f"⏱️  Time: {avg_time_improvement:.1f}% faster")
    print(f"🧠 Memory: {avg_memory_improvement:.1f}% more efficient")
    
    return results

if __name__ == "__main__":
    # Run the benchmark
    results = run_comprehensive_benchmark()
    
    print("\n✅ Benchmark completed successfully!")
    print("📝 Results saved to benchmark results.")
#!/usr/bin/env python3
"""Validate data source configuration for the SubSkin project.

This script validates the data source configuration file and tests
the data source manager functionality.
"""

import sys
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from src.utils.data_source_manager import DataSourceManager
from src.models.data_source import DataSourceCategory, DataSourceType, AccessMethod, PriorityLevel


def validate_configuration() -> bool:
    """Validate the data source configuration."""
    print("=" * 60)
    print("VALIDATING DATA SOURCE CONFIGURATION")
    print("=" * 60)
    
    try:
        manager = DataSourceManager()
        print("✓ Configuration file loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False
    
    # Print summary
    manager.print_summary()
    
    # Test basic queries
    print("\n" + "=" * 60)
    print("TESTING BASIC QUERIES")
    print("=" * 60)
    
    # Test: Get all sources
    all_sources = manager.get_all_sources()
    print(f"✓ Total data sources: {len(all_sources)}")
    
    # Test: Get priority sources
    priority_1 = manager.get_priority_1_sources()
    priority_2 = manager.get_priority_2_sources()
    priority_3 = manager.get_priority_3_sources()
    print(f"✓ Priority 1 sources: {len(priority_1)}")
    print(f"✓ Priority 2 sources: {len(priority_2)}")
    print(f"✓ Priority 3 sources: {len(priority_3)}")
    
    # Test: Get by category
    for category in DataSourceCategory:
        sources = manager.get_sources_by_category(category)
        category_info = manager.get_category_info(category)
        if category_info:
            print(f"✓ {category_info.name}: {len(sources)} sources")
    
    # Test: Find specific sources
    test_sources = ["pubmed", "clinicaltrials_gov", "bbsls"]
    for source_id in test_sources:
        source = manager.get_source(source_id)
        if source:
            print(f"✓ Found source '{source_id}': {source.name}")
        else:
            print(f"✗ Source '{source_id}' not found")
    
    # Test: Generate collection plan
    plan = manager.generate_collection_plan()
    print(f"✓ Generated collection plan with {sum(len(p['sources']) for p in plan.values())} sources")
    
    # Test: Get quality standards
    standards = manager.get_quality_standards()
    if standards:
        print(f"✓ Quality standards loaded: {len(standards.source_credibility)} credibility criteria")
    
    return True


def test_individual_sources() -> bool:
    """Test individual data source validation."""
    print("\n" + "=" * 60)
    print("TESTING INDIVIDUAL DATA SOURCES")
    print("=" * 60)
    
    try:
        manager = DataSourceManager()
    except Exception as e:
        print(f"✗ Failed to load manager: {e}")
        return False
    
    all_ok = True
    
    for source in manager.get_all_sources():
        print(f"\nSource: {source.name} ({source.id})")
        print(f"  Category: {source.category.value}")
        print(f"  Type: {source.type.value}")
        print(f"  Priority: {source.priority.value}")
        print(f"  Access: {source.access_method.value}")
        print(f"  Quality: {source.data_quality}/5")
        
        # Validate URL
        if not source.url.startswith(("http://", "https://")):
            print(f"  ✗ Invalid URL: {source.url}")
            all_ok = False
        else:
            print(f"  ✓ URL valid")
        
        # Validate data quality
        if not 1 <= source.data_quality <= 5:
            print(f"  ✗ Invalid data quality: {source.data_quality}")
            all_ok = False
        else:
            print(f"  ✓ Data quality valid")
        
        # Get recommended tools
        tools = source.get_collection_tools()
        if tools:
            print(f"  ✓ Recommended tools: {', '.join(tools)}")
        else:
            print(f"  ⚠ No recommended tools specified")
    
    return all_ok


def check_priority_coverage() -> bool:
    """Check that priority groups have good coverage."""
    print("\n" + "=" * 60)
    print("CHECKING PRIORITY COVERAGE")
    print("=" * 60)
    
    try:
        manager = DataSourceManager()
    except Exception as e:
        print(f"✗ Failed to load manager: {e}")
        return False
    
    plan = manager.generate_collection_plan()
    
    for priority_level, priority_data in plan.items():
        print(f"\n{priority_data['name']}:")
        print(f"  Sources: {len(priority_data['sources'])}")
        print(f"  Estimated volume: {priority_data['estimated_volume']}")
        print(f"  Tools needed: {', '.join(priority_data['tools_needed'])}")
        
        # Check category coverage
        categories = set()
        types = set()
        for source in priority_data['sources']:
            categories.add(source['category'])
            types.add(source['type'])
        
        print(f"  Categories covered: {len(categories)}")
        print(f"  Source types: {len(types)}")
    
    return True


def main() -> int:
    """Main validation function."""
    print("SubSkin Data Source Configuration Validator")
    print("Version: 1.0.0")
    print()
    
    # Check if configuration file exists
    config_path = Path(__file__).parent.parent / "configs" / "data_sources.yaml"
    if not config_path.exists():
        print(f"Error: Configuration file not found at {config_path}")
        return 1
    
    print(f"Using configuration file: {config_path}")
    print()
    
    # Run all validation tests
    tests = [
        ("Configuration validation", validate_configuration),
        ("Individual source testing", test_individual_sources),
        ("Priority coverage check", check_priority_coverage),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✓ {test_name} passed")
            else:
                print(f"✗ {test_name} failed")
        except Exception as e:
            print(f"✗ {test_name} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    if passed == total:
        print("\n✅ All tests passed! Data source configuration is valid.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
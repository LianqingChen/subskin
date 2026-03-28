"""Data source manager for the SubSkin project.

This module provides functionality for loading, managing, and querying data sources
defined in the data_sources.yaml configuration file.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from src.models.data_source import (
    DataSource,
    DataSourceCategory,
    DataSourceCategoryInfo,
    PriorityGroup,
    CollectionStrategy,
    QualityStandard,
    PriorityLevel,
    DataSourceType,
    AccessMethod,
)


@dataclass
class DataSourceConfig:
    """Complete data source configuration."""
    
    categories: Dict[str, DataSourceCategoryInfo]
    data_sources: Dict[str, DataSource]
    priority_groups: Dict[str, PriorityGroup]
    collection_strategies: Dict[str, CollectionStrategy]
    quality_standards: QualityStandard
    metadata: Dict[str, Any]
    
    def get_priority_sources(self, priority: PriorityLevel) -> List[DataSource]:
        """Get all data sources with the specified priority level."""
        group = self.priority_groups.get(priority.value)
        if not group:
            return []
        
        return [
            self.data_sources[source_id]
            for source_id in group.data_sources
            if source_id in self.data_sources
        ]
    
    def get_sources_by_category(self, category: DataSourceCategory) -> List[DataSource]:
        """Get all data sources in the specified category."""
        return [
            source for source in self.data_sources.values()
            if source.category == category
        ]
    
    def get_sources_by_type(self, source_type: DataSourceType) -> List[DataSource]:
        """Get all data sources of the specified type."""
        return [
            source for source in self.data_sources.values()
            if source.type == source_type
        ]
    
    def get_sources_by_access_method(self, method: AccessMethod) -> List[DataSource]:
        """Get all data sources using the specified access method."""
        return [
            source for source in self.data_sources.values()
            if source.access_method == method
        ]
    
    def find_source_by_name(self, name: str) -> Optional[DataSource]:
        """Find a data source by name (case-insensitive)."""
        name_lower = name.lower()
        for source in self.data_sources.values():
            if source.name.lower() == name_lower:
                return source
        return None
    
    def get_category_info(self, category: DataSourceCategory) -> Optional[DataSourceCategoryInfo]:
        """Get information about a specific category."""
        return self.categories.get(category.value)
    
    def validate_configuration(self) -> List[str]:
        """Validate the configuration and return any issues."""
        issues = []
        
        # Check that all priority group references are valid
        for group_id, group in self.priority_groups.items():
            for source_id in group.data_sources:
                if source_id not in self.data_sources:
                    issues.append(f"Priority group '{group_id}' references unknown data source '{source_id}'")
        
        # Check that all data sources have valid categories
        for source_id, source in self.data_sources.items():
            if source.category.value not in self.categories:
                issues.append(f"Data source '{source_id}' has unknown category '{source.category.value}'")
        
        return issues


class DataSourceManager:
    """Manager for data source configuration and queries."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the data source manager.
        
        Args:
            config_path: Path to the data_sources.yaml configuration file.
                        If None, uses the default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "configs" / "data_sources.yaml"
        
        self.config_path = config_path
        self.config: Optional[DataSourceConfig] = None
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load and parse the data source configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Data source configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # Parse categories
        categories = {}
        for cat_data in config_data.get('categories', []):
            category = DataSourceCategoryInfo(**cat_data)
            categories[category.id] = category
        
        # Parse data sources
        data_sources = {}
        for source_data in config_data.get('data_sources', []):
            # Convert string enums to enum instances
            source_data = self._convert_enums(source_data)
            source = DataSource(**source_data)
            data_sources[source.id] = source
        
        # Parse priority groups
        priority_groups = {}
        for group_id, group_data in config_data.get('priority_groups', {}).items():
            group_data['data_sources'] = group_data.get('data_sources', [])
            group = PriorityGroup(**group_data)
            priority_groups[group_id] = group
        
        # Parse collection strategies
        collection_strategies = {}
        for strategy_id, strategy_data in config_data.get('collection_strategies', {}).items():
            strategy_data['id'] = strategy_id
            strategy = CollectionStrategy(**strategy_data)
            collection_strategies[strategy_id] = strategy
        
        # Parse quality standards
        quality_data = config_data.get('quality_standards', {})
        quality_standards = QualityStandard(**quality_data)
        
        # Get metadata
        metadata = config_data.get('metadata', {})
        
        self.config = DataSourceConfig(
            categories=categories,
            data_sources=data_sources,
            priority_groups=priority_groups,
            collection_strategies=collection_strategies,
            quality_standards=quality_standards,
            metadata=metadata,
        )
        
        # Validate configuration
        issues = self.config.validate_configuration()
        if issues:
            print(f"Warning: {len(issues)} configuration issues found:")
            for issue in issues:
                print(f"  - {issue}")
    
    def _convert_enums(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert string values to enum instances where appropriate."""
        enum_mappings = {
            'category': DataSourceCategory,
            'type': DataSourceType,
            'access_method': AccessMethod,
            'cost': {
                'free': 'free',
                'paid_subscription': 'paid_subscription',
                'freemium': 'freemium',
                'institutional_access': 'institutional_access',
            },
            'priority': PriorityLevel,
            'collection_method': {
                'api_crawling': 'api_crawling',
                'web_scraping': 'web_scraping',
                'direct_download': 'direct_download',
                'web_download': 'web_download',
                'git_clone': 'git_clone',
            },
        }
        
        result = data.copy()
        
        for field_name, enum_type in enum_mappings.items():
            if field_name in result and isinstance(result[field_name], str):
                if field_name in ['cost', 'collection_method']:
                    # These are mappings from config values to enum values
                    mapping = enum_type
                    str_value = result[field_name]
                    if str_value in mapping:
                        result[field_name] = str_value
                else:
                    # These are direct enum types
                    str_value = result[field_name]
                    try:
                        result[field_name] = enum_type(str_value)
                    except ValueError:
                        # If value doesn't match enum, keep as string
                        pass
        
        return result
    
    def get_all_sources(self) -> List[DataSource]:
        """Get all data sources."""
        if not self.config:
            return []
        return list(self.config.data_sources.values())
    
    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a specific data source by ID."""
        if not self.config:
            return None
        return self.config.data_sources.get(source_id)
    
    def get_priority_1_sources(self) -> List[DataSource]:
        """Get all priority 1 (immediate collection) data sources."""
        if not self.config:
            return []
        return self.config.get_priority_sources(PriorityLevel.PRIORITY_1)
    
    def get_priority_2_sources(self) -> List[DataSource]:
        """Get all priority 2 (secondary collection) data sources."""
        if not self.config:
            return []
        return self.config.get_priority_sources(PriorityLevel.PRIORITY_2)
    
    def get_priority_3_sources(self) -> List[DataSource]:
        """Get all priority 3 (long-term planning) data sources."""
        if not self.config:
            return []
        return self.config.get_priority_sources(PriorityLevel.PRIORITY_3)
    
    def get_sources_by_category(self, category: DataSourceCategory) -> List[DataSource]:
        """Get all data sources in the specified category."""
        if not self.config:
            return []
        return self.config.get_sources_by_category(category)
    
    def get_sources_by_type(self, source_type: DataSourceType) -> List[DataSource]:
        """Get all data sources of the specified type."""
        if not self.config:
            return []
        return self.config.get_sources_by_type(source_type)
    
    def get_sources_by_access_method(self, method: AccessMethod) -> List[DataSource]:
        """Get all data sources using the specified access method."""
        if not self.config:
            return []
        return self.config.get_sources_by_access_method(method)
    
    def find_source_by_name(self, name: str) -> Optional[DataSource]:
        """Find a data source by name (case-insensitive)."""
        if not self.config:
            return None
        return self.config.find_source_by_name(name)
    
    def get_category_info(self, category: DataSourceCategory) -> Optional[DataSourceCategoryInfo]:
        """Get information about a specific category."""
        if not self.config:
            return None
        return self.config.get_category_info(category)
    
    def get_collection_strategy(self, strategy_id: str) -> Optional[CollectionStrategy]:
        """Get a collection strategy by ID."""
        if not self.config:
            return None
        return self.config.collection_strategies.get(strategy_id)
    
    def get_quality_standards(self) -> Optional[QualityStandard]:
        """Get the quality standards."""
        if not self.config:
            return None
        return self.config.quality_standards
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get configuration metadata."""
        if not self.config:
            return {}
        return self.config.metadata
    
    def generate_collection_plan(self) -> Dict[str, Any]:
        """Generate a data collection plan based on priorities."""
        if not self.config:
            return {}
        
        plan = {
            'priority_1': {
                'name': '立即采集 (核心数据源)',
                'sources': [],
                'estimated_volume': 0,
                'tools_needed': set(),
            },
            'priority_2': {
                'name': '次阶段采集 (补充数据源)',
                'sources': [],
                'estimated_volume': 0,
                'tools_needed': set(),
            },
            'priority_3': {
                'name': '长期规划 (扩展数据源)',
                'sources': [],
                'estimated_volume': 0,
                'tools_needed': set(),
            },
        }
        
        for source in self.get_all_sources():
            priority = source.priority.value
            source_info = {
                'id': source.id,
                'name': source.name,
                'category': source.category.value,
                'type': source.type.value,
                'access_method': source.access_method.value,
                'collection_method': source.collection_method.value,
                'estimated_volume': source.estimated_volume or 0,
                'tools': source.get_collection_tools(),
                'requires_ethical_considerations': source.requires_ethical_considerations(),
            }
            
            plan[priority]['sources'].append(source_info)
            plan[priority]['estimated_volume'] += source_info['estimated_volume']
            plan[priority]['tools_needed'].update(source_info['tools'])
        
        # Convert sets to lists for JSON serialization
        for priority in plan:
            plan[priority]['tools_needed'] = list(plan[priority]['tools_needed'])
        
        return plan
    
    def print_summary(self) -> None:
        """Print a summary of the data source configuration."""
        if not self.config:
            print("No configuration loaded.")
            return
        
        print("=" * 60)
        print("DATA SOURCE CONFIGURATION SUMMARY")
        print("=" * 60)
        print(f"Total data sources: {len(self.config.data_sources)}")
        print(f"Categories: {len(self.config.categories)}")
        print(f"Priority groups: {len(self.config.priority_groups)}")
        print()
        
        # Print by priority
        for priority in [PriorityLevel.PRIORITY_1, PriorityLevel.PRIORITY_2, PriorityLevel.PRIORITY_3]:
            sources = self.config.get_priority_sources(priority)
            group = self.config.priority_groups.get(priority.value)
            if group:
                print(f"{group.name}: {len(sources)} sources")
                for source in sources:
                    print(f"  - {source.name} ({source.id})")
                print()
        
        # Print by category
        print("By Category:")
        for category_id, category_info in self.config.categories.items():
            sources = [
                s for s in self.config.data_sources.values()
                if s.category.value == category_id
            ]
            print(f"  {category_info.name}: {len(sources)} sources")
        
        print("=" * 60)
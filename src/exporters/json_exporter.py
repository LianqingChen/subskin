"""JSON exporter for SubSkin project.

This module provides a JSONExporter that exports crawled paper and trial
data to JSON files with proper date-based directory structure and
serialization of datetime objects.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Union, Dict, Any, Optional
from src.models.paper import Paper
from src.models.trial import ClinicalTrial

logger = logging.getLogger(__name__)


class JSONExporter:
    def __init__(self, export_dir: Optional[Path] = None):
        self.export_dir = export_dir or Path("data/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_date_dir(self, date: Optional[datetime] = None) -> Path:
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return self.export_dir / date_str
    
    def _serialize_paper(self, paper: Paper) -> Dict[str, Any]:
        data = paper.model_dump()
        data["crawled_at"] = paper.crawled_at.isoformat() if paper.crawled_at else None
        data["source"] = paper.source.value if hasattr(paper.source, "value") else paper.source
        return data
    
    def _serialize_trial(self, trial: ClinicalTrial) -> Dict[str, Any]:
        data = trial.model_dump()
        data["crawled_at"] = trial.crawled_at.isoformat() if trial.crawled_at else None
        return data
    
    def export_papers(
        self, 
        papers: List[Paper], 
        filename: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> Path:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"papers_{timestamp}.json"
        
        output_path = date_dir / filename
        
        serialized = [self._serialize_paper(paper) for paper in papers]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Exported {len(papers)} papers to {output_path}")
        return output_path
    
    def export_trials(
        self, 
        trials: List[ClinicalTrial], 
        filename: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> Path:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"trials_{timestamp}.json"
        
        output_path = date_dir / filename
        
        serialized = [self._serialize_trial(trial) for trial in trials]
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Exported {len(trials)} trials to {output_path}")
        return output_path
    
    def export_deduplicated_papers(
        self,
        papers: List[Paper],
        source_info: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> Path:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        source_suffix = f"_{source_info}" if source_info else ""
        filename = f"deduplicated_papers{source_suffix}_{timestamp}.json"
        
        output_path = date_dir / filename
        
        serialized = [self._serialize_paper(paper) for paper in papers]
        
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "paper_count": len(papers),
            "source_info": source_info,
            "deduplicated": True
        }
        
        export_data = {
            "metadata": metadata,
            "papers": serialized
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Exported {len(papers)} deduplicated papers to {output_path}")
        return output_path
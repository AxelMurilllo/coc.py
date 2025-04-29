"""
MIT License

Copyright (c) 2019-2020 mathsman5133

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import orjson
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Type, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .building import Building

from .abc import DataContainer

logger = logging.getLogger(__name__)

# Path for townhall levels json
TOWNHALL_LEVELS_FILE_PATH = Path(__file__).parent.joinpath(Path("static/townhall_levels.json"))

class TownHallLevel:
    """Represents a specific Town Hall level and its building requirements.
    
    This class tracks what buildings are unlocked at this level and their maximum counts.
    It also maintains cumulative counts from previous levels.
    
    Attributes
    ----------
    level: :class:`int`
        The town hall level
    attack_cost: :class:`int`
        Cost in resources to attack at this town hall level
    new_buildings: Dict[:class:`str`, :class:`int`]
        New buildings unlocked at this level and their counts
    cumulative_buildings: Dict[:class:`str`, :class:`int`]
        Total allowed building counts including previous levels
    storage_info: Dict[:class:`str`, :class:`int`]
        Storage and loot-related attributes for this level
    """
    def __init__(self, level: int, data: dict):
        self.level = level
        
        # Get first key which contains the actual data
        first_key = next(iter(data))
        level_data = data[first_key]
        
        self.attack_cost = level_data.get("AttackCost", 0)
        
        # Storage and loot info
        self.storage_info = {
            "resource_storage_loot_percentage": level_data.get("ResourceStorageLootPercentage", 0),
            "dark_elixir_storage_loot_percentage": level_data.get("DarkElixirStorageLootPercentage", 0),
            "resource_storage_loot_cap": level_data.get("ResourceStorageLootCap", 0),
            "dark_elixir_storage_loot_cap": level_data.get("DarkElixirStorageLootCap", 0),
            "war_prize_resource_cap": level_data.get("WarPrizeResourceCap", 0),
            "war_prize_dark_elixir_cap": level_data.get("WarPrizeDarkElixirCap", 0)
        }
        
        # Extract new building unlocks for this level
        self.new_buildings = {}
        self.cumulative_buildings = {}
        
        for key, value in level_data.items():
            # Skip non-building keys
            if key in [
                "Name", "AttackCost", "ResourceStorageLootPercentage", 
                "DarkElixirStorageLootPercentage", "ResourceStorageLootCap",
                "DarkElixirStorageLootCap", "WarPrizeResourceCap", 
                "WarPrizeDarkElixirCap", "WarPrizeCommonOreCap",
                "WarPrizeRareOreCap", "WarPrizeEpicOreCap",
                "LegendPrizeGoldCap", "LegendPrizeElixirCap",
                "LegendPrizeDarkElixirCap", "WarPrizeAllianceExpCap",
                "CartLootCapResource", "CartLootReengagementResource",
                "CartLootCapDarkElixir", "CartLootReengagementDarkElixir",
                "ReengagementBuildingBudget", "ReengagementHeroBudget",
                "ReengagementWallBudget", "ReengagementLabBudget",
                "HeroBoostHours", "PowerBoostHours", "ResourceProductionBoostHours",
                "StarBonusBoostHours", "StrengthMaxTroopTypes",
                "StrengthMaxSpellTypes", "StrengthMaxSiegeTypes",
                "TreasuryWarGold", "TreasuryWarElixir", "TreasuryWarDarkElixir",
                "FriendlyCost", "PackElixir", "PackGold", "PackDarkElixir",
                "PackGold2", "PackElixir2", "DuelPrizeResourceCap",
                "AttackCostVillage2", "ElixirCartStorageCap",
                "ResourceScalingPercentage", "ResourceScalingPercentage2"
            ]:
                continue
                
            try:
                self.new_buildings[key] = int(value)
            except (ValueError, TypeError):
                continue

    def __repr__(self):
        return f"<TownHallLevel level={self.level}>"

class TownHall:
    """Represents the Town Hall building and manages level requirements.
    
    This class handles loading and tracking town hall level requirements,
    including cumulative building counts and validation of requirements.
    
    Attributes
    ----------
    levels: Dict[:class:`int`, :class:`TownHallLevel`]
        Mapping of town hall levels to their requirement data
    cumulative_requirements: Dict[:class:`int`, Dict[:class:`str`, :class:`int`]]
        Cumulative building requirements for each town hall level
    """
    def __init__(self):
        self.levels: Dict[int, TownHallLevel] = {}
        self.cumulative_requirements: Dict[int, Dict[str, int]] = {}
        self._load_requirements()
        
    def _load_requirements(self):
        """Load town hall requirements from JSON file and calculate cumulative requirements."""
        try:
            with open(TOWNHALL_LEVELS_FILE_PATH, "rb") as fp:
                data = orjson.loads(fp.read())
                
            # Load each town hall level
            for th_level, level_data in data.items():
                th_level = int(th_level)
                self.levels[th_level] = TownHallLevel(th_level, level_data)
                
            # Calculate cumulative requirements
            for level in range(1, max(self.levels.keys()) + 1):
                if level not in self.levels:
                    continue
                    
                cumulative = {}
                # Add requirements from all previous levels
                for prev_level in range(1, level + 1):
                    if prev_level not in self.levels:
                        continue
                    for building, count in self.levels[prev_level].new_buildings.items():
                        cumulative[building] = cumulative.get(building, 0) + count
                        
                self.cumulative_requirements[level] = cumulative
                
        except Exception as e:
            logger.error(f"Error loading townhall requirements: {e}")
            self.levels = {}
            self.cumulative_requirements = {}
            
    def get_max_building_count(self, building_name: str, th_level: int) -> int:
        """Get the maximum allowed count of a building at a specific town hall level.
        
        Parameters
        ----------
        building_name: :class:`str`
            The name of the building to check
        th_level: :class:`int`
            The town hall level to check
            
        Returns
        -------
        :class:`int`
            The maximum allowed count of the building, or 0 if not available
        """
        if th_level not in self.cumulative_requirements:
            return 0
            
        return self.cumulative_requirements[th_level].get(building_name, 0)
        
    def get_new_buildings(self, th_level: int) -> Dict[str, int]:
        """Get new buildings unlocked at a specific town hall level.
        
        Parameters
        ----------
        th_level: :class:`int`
            The town hall level to check
            
        Returns
        -------
        Dict[:class:`str`, :class:`int`]
            Dictionary of building names to counts unlocked at this level
        """
        if th_level not in self.levels:
            return {}
            
        return dict(self.levels[th_level].new_buildings)
        
    def get_cumulative_requirements(self, th_level: int) -> Dict[str, int]:
        """Get cumulative building requirements up to a specific town hall level.
        
        Parameters
        ----------
        th_level: :class:`int`
            The town hall level to check
            
        Returns
        -------
        Dict[:class:`str`, :class:`int`]
            Dictionary of building names to total allowed counts
        """
        if th_level not in self.cumulative_requirements:
            return {}
            
        return dict(self.cumulative_requirements[th_level])
        
    def validate_buildings(self, buildings: List[Any], th_level: int) -> bool:
        """Check if a list of buildings meets the requirements for a town hall level.
        
        Parameters
        ----------
        buildings: List[:class:`Building`]
            The list of buildings to validate
        th_level: :class:`int`
            The town hall level to check against
            
        Returns
        -------
        :class:`bool`
            True if the buildings meet all requirements
        """
        if th_level not in self.cumulative_requirements:
            return False
            
        # Count buildings by name
        building_counts = {}
        for building in buildings:
            if not building.is_home_base:
                continue
            building_counts[building.name] = building_counts.get(building.name, 0) + 1
            
        # Check against requirements
        requirements = self.cumulative_requirements[th_level]
        for building_name, required_count in requirements.items():
            if building_counts.get(building_name, 0) < required_count:
                return False
                
        return True
        
    def get_missing_requirements(self, buildings: List[Any], th_level: int) -> Dict[str, int]:
        """Get missing or under-count buildings for a town hall level.
        
        Parameters
        ----------
        buildings: List[:class:`Building`]
            The list of buildings to check
        th_level: :class:`int`
            The town hall level to check against
            
        Returns
        -------
        Dict[:class:`str`, :class:`int`]
            Dictionary of building names to counts that are missing
        """
        if th_level not in self.cumulative_requirements:
            return {}
            
        # Count buildings by name
        building_counts = {}
        for building in buildings:
            if not building.is_home_base:
                continue
            building_counts[building.name] = building_counts.get(building.name, 0) + 1
            
        # Check against requirements
        missing = {}
        requirements = self.cumulative_requirements[th_level]
        for building_name, required_count in requirements.items():
            current_count = building_counts.get(building_name, 0)
            if current_count < required_count:
                missing[building_name] = required_count - current_count
                
        return missing 
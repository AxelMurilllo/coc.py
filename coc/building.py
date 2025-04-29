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

from typing import Dict, List, Optional, Type, Any, Set
from pathlib import Path
import logging

from .abc import DataContainer, DataContainerHolder
from .enums import Resource
from .miscmodels import TimeDelta, try_enum
from .utils import UnitStat, BuildingStat
from .townhall import TownHall

# Path is already defined in abc.py
from .abc import BUILDING_FILE_PATH

# Add path for townhall levels json
TOWNHALL_LEVELS_FILE_PATH = Path(__file__).parent.joinpath(Path("static/townhall_levels.json"))

logger = logging.getLogger(__name__)

class Building(DataContainer):
    """Represents a Building object filled with game data from static files.

    Attributes
    ----------
    id: :class:`int`
        The building's unique ID.
    name: :class:`str`
        The building's name.
    hitpoints: :class:`int`
        The number of hitpoints the building has at this level.
    width: :class:`int`
        The width of the building in tiles.
    height: :class:`int`
        The height of the building in tiles.
    build_cost: :class:`int`
        The amount of resources required to build the building.
    build_resource: :class:`Resource`
        The type of resource used to build this building.
    build_time: :class:`TimeDelta`
        The time taken to build this building.
    upgrade_cost: :class:`int`
        The amount of resources required to upgrade the building to the next level.
    upgrade_resource: :class:`Resource`
        The type of resource used to upgrade this building.
    upgrade_time: :class:`TimeDelta`
        The time taken to upgrade this building to the next level.
    required_th_level: :class:`int`
        The minimum required townhall level for this building/level.
    regeneration_time: :class:`TimeDelta`
        The time required for this building to regenerate if it has regeneration properties.
    dps: :class:`int`
        The damage per second of the building (for defensive buildings).
    is_defensive: :class:`bool`
        Whether this building is a defensive building.
    is_resource: :class:`bool`
        Whether this building is a resource building.
    is_army: :class:`bool`
        Whether this building is an army building.
    is_trap: :class:`bool`
        Whether this building is a trap.
    is_wall: :class:`bool`
        Whether this building is a wall.
    is_supercharged: :class:`bool`
        Whether this building is currently supercharged.
    supercharge_level: :class:`int`
        The current supercharge level, if any.
    is_loaded: :class:`bool`
        Whether the API data has been loaded for this building.
    level: :class:`int`
        The building's level
    max_level: :class:`int`
        The max level for this building.
    village: :class:`str`
        Either ``home`` or ``builderBase``, indicating which village this building belongs to.
    """
    name: str
    level: int
    max_level: int
    village: str

    id: int
    hitpoints: int
    width: int
    height: int
    build_cost: int
    build_resource: "Resource"
    build_time: "TimeDelta"
    upgrade_cost: int
    upgrade_resource: "Resource"
    upgrade_time: "TimeDelta"
    required_th_level: int
    regeneration_time: "TimeDelta"
    
    # For defensive buildings
    dps: int
    
    # Building type flags
    is_defensive: bool = False
    is_resource: bool = False
    is_army: bool = False
    is_trap: bool = False
    is_wall: bool = False
    is_home_village: bool = False
    is_builder_base: bool = False
    is_town_hall: bool = False
    is_builder_hall: bool = False
    
    # Supercharge attributes
    is_supercharged: bool = False
    supercharge_level: int = 0
    
    # Internal TH requirement keys
    _internal_name: str = None
    _townhall = TownHall()
    
    is_loaded: bool = False

    def __repr__(self):
        attrs = [
            ("name", self.name),
            ("id", self.id),
            ("level", self.level),
        ]
        return "<%s %s>" % (
            self.__class__.__name__, " ".join("%s=%r" % t for t in attrs),)

    @classmethod
    def _load_json_meta(cls, json_meta: dict, id, name: str, th_to_level_map):
        """Load building data from JSON.
        
        This method processes the building data from the static JSON files and
        sets the appropriate attributes on the Building class.
        """
        cls.id = int(id)
        cls.name = name
        
        # Store internal name for townhall level lookups
        cls._internal_name = json_meta.get("Name", name.replace(" ", ""))
        
        # Get all numeric keys and sort them
        levels_available = sorted([int(key) for key in json_meta.keys() if key.isnumeric()])
        max_level = max(levels_available)
        
        # Create stats arrays starting at level 0 (unbuilt)
        hitpoints_list = [0]  # Level 0 has 0 hitpoints
        upgrade_costs = []  # Will be populated with costs to reach next level
        upgrade_times = []  # Will be populated with times to reach next level
        th_requirements = [1]  # Level 0 requires TH1
        regeneration_times = [0]  # Level 0 has no regen
        dps_list = [0]  # Level 0 has no DPS
        
        # For each level from 0 to max_level
        for level in range(max_level):
            current_json_level = str(level + 1)  # JSON uses 1-based indexing
            level_data = json_meta.get(current_json_level, {})
            
            # Add stats for current level
            hitpoints_list.append(level_data.get("Hitpoints", 0))
            th_requirements.append(level_data.get("TownHallLevel", 1))
            regeneration_times.append(level_data.get("RegenTime", 0))
            dps_list.append(level_data.get("DPS", 0))
            
            # Get cost and time to reach next level
            next_json_level = str(level + 2)  # Look ahead one level
            if next_json_level in json_meta:
                next_level_data = json_meta.get(next_json_level, {})
                upgrade_costs.append(next_level_data.get("BuildCost", 0))
                upgrade_times.append(TimeDelta(
                    days=next_level_data.get("BuildTimeD", 0),
                    hours=next_level_data.get("BuildTimeH", 0),
                    minutes=next_level_data.get("BuildTimeM", 0),
                    seconds=next_level_data.get("BuildTimeS", 0)
                ))
            else:
                # Max level has no upgrade cost/time
                upgrade_costs.append(0)
                upgrade_times.append(TimeDelta())
        
        # Insert build cost/time at the start (level 0 -> 1)
        level_1_data = json_meta.get("1", {})
        upgrade_costs.insert(0, level_1_data.get("BuildCost", 0))
        upgrade_times.insert(0, TimeDelta(
            days=level_1_data.get("BuildTimeD", 0),
            hours=level_1_data.get("BuildTimeH", 0),
            minutes=level_1_data.get("BuildTimeM", 0),
            seconds=level_1_data.get("BuildTimeS", 0)
        ))
        
        # Set all the stats using BuildingStat instead of UnitStat
        cls.max_level = max_level
        cls.hitpoints = try_enum(BuildingStat, hitpoints_list)
        cls.level = cls.hitpoints and BuildingStat(range(0, len(hitpoints_list)))  # Start from 0
        
        # Building dimensions - get from top level attributes since they don't change per level
        cls.width = json_meta.get("Width", 1)
        cls.height = json_meta.get("Height", 1)
        
        # Build cost and time (cost and time to go from level 0 to 1)
        cls.build_cost = level_1_data.get("BuildCost", 0)
        build_resource_str = level_1_data.get("BuildResource", "Gold")
        cls.build_resource = Resource(value=build_resource_str)
        
        cls.build_time = TimeDelta(
            days=level_1_data.get("BuildTimeD", 0),
            hours=level_1_data.get("BuildTimeH", 0),
            minutes=level_1_data.get("BuildTimeM", 0),
            seconds=level_1_data.get("BuildTimeS", 0)
        )
        
        # Store upgrade costs and times using BuildingStat
        cls.upgrade_cost = try_enum(BuildingStat, upgrade_costs)
        cls.upgrade_resource = Resource(value=level_1_data.get("BuildResource", "Gold"))
        cls.upgrade_time = try_enum(BuildingStat, upgrade_times)
        
        # Store other stats using BuildingStat
        cls.required_th_level = try_enum(BuildingStat, th_requirements)
        cls.regeneration_time = try_enum(BuildingStat, regeneration_times)
        cls.dps = try_enum(BuildingStat, dps_list)
        
        # Village type
        cls._is_home_village = False if json_meta.get("VillageType") else True
        cls.village = "home" if cls._is_home_village else "builderBase"
        
        # Set building type flags based on building class and preview scenario
        building_class = json_meta.get("1", {}).get("BuildingClass", "")
        preview_scenario = json_meta.get("PreviewScenario", "")
        shop_building_class = json_meta.get("1", {}).get("ShopBuildingClass", "")

        # Defensive buildings
        cls.is_defensive = (
            building_class in ["Defense", "Defensive"] or
            shop_building_class == "Defense" or
            preview_scenario in ["Defense", "AirAndGroundDefense", "AirDefense", "DefensiveBuilder"]
        )

        # Resource buildings
        cls.is_resource = (
            building_class in ["Resource", "ResourceBuilding"] or
            json_meta.get("1", {}).get("SecondaryTargetingClass") == "Resource"
        )

        # Army buildings
        cls.is_army = (
            building_class in ["Army", "ArmyBuilding", "Barrack", "Laboratory"] or
            shop_building_class == "Army" or
            json_meta.get("1", {}).get("IsHeroBarrack", False)
        )

        # Trap buildings
        cls.is_trap = building_class == "Trap"

        # Wall buildings
        cls.is_wall = (
            building_class == "Wall" or
            preview_scenario == "WallPieces"
        )

        # Special building types
        if name == "Town Hall":
            cls.is_town_hall = True
        elif name == "Builder Hall":
            cls.is_builder_hall = True
        elif building_class == "Worker2":
            cls.is_builder = True
        elif building_class == "Npc":
            cls.is_npc = True
        elif building_class == "Helper":
            cls.is_helper = True
        elif preview_scenario == "ClanCastle" or "Clan Castle" in name:
            cls.is_clan_castle = True
        
        cls.is_loaded = True
        return cls
    
    @property
    def is_max(self) -> bool:
        """:class:`bool`: Returns a boolean that indicates whether the building is at max level"""
        return self.max_level == self.level
    
    @property
    def is_builder_base(self) -> bool:
        """:class:`bool`: Returns a boolean that indicates whether the building belongs to the builder base."""
        return self.village == "builderBase"
    
    @property
    def is_home_base(self) -> bool:
        """:class:`bool`: Returns a boolean that indicates whether the building belongs to the home base."""
        return self.village == "home"
    
    def is_max_for_townhall(self, townhall_level: int = None) -> bool:
        """:class:`bool`: Returns whether the building is the max level for the given townhall level.
        
        Parameters
        ----------
        townhall_level: :class:`int`
            The townhall level to check against. If None, uses the building's _townhall attribute.
        """
        if self.is_max:
            return True
        
        th_level = townhall_level or getattr(self, "_townhall", 0)
        if not th_level:
            return False
        
        # Get max level for this building at this TH level
        max_level_at_th = self.__class__.get_max_level_at_townhall(th_level)
        if max_level_at_th is None:
            return False
        
        return self.level >= max_level_at_th
    
    @classmethod
    def get_max_level_at_townhall(cls, townhall_level: int) -> Optional[int]:
        """Get the maximum level this building can be at a specific townhall level.
        
        Parameters
        ----------
        townhall_level: :class:`int`
            The townhall level to check.
            
        Returns
        -------
        Optional[:class:`int`]
            The maximum level this building can be at the given townhall level, or None if not available.
        """
        if not cls._townhall:
            return None
            
        return cls._townhall.get_max_building_count(cls.name, townhall_level)
    
    def is_valid_for_townhall(self, townhall_level: int) -> bool:
        """Check if this building is valid for the given townhall level.
        
        Parameters
        ----------
        townhall_level: :class:`int`
            The townhall level to check against.
            
        Returns
        -------
        :class:`bool`
            True if this building is valid for the given townhall level.
        """
        max_level = self.__class__.get_max_level_at_townhall(townhall_level)
        
        # If max_level is None, this building isn't available at this TH level
        if max_level is None:
            return False
            
        # Check if the building's level is within the allowed range
        return 1 <= self.level <= max_level
    
    def get_supercharge_stats(self) -> Dict[str, int]:
        """Get supercharge stats for this building.
        
        Returns
        -------
        :class:`Dict[str, int]`
            A dictionary containing supercharged stats (hitpoints, dps, etc.)
        """
        if not self.is_supercharged:
            return {}
            
        # Calculate supercharged stats based on level and supercharge_level
        # This is a placeholder - actual implementation would use game data
        # TODO: Implement actual supercharge stats
        supercharge_multiplier = 1.0 + (0.1 * self.supercharge_level)
        
        stats = {}
        if hasattr(self, "hitpoints") and self.hitpoints:
            stats["hitpoints"] = int(self.hitpoints[self.level] * supercharge_multiplier)
        
        if hasattr(self, "dps") and self.dps and self.is_defensive:
            stats["dps"] = int(self.dps[self.level] * supercharge_multiplier)
            
        return stats


class BuildingHolder(DataContainerHolder):
    """Holder for all buildings in the game."""
    def __init__(self):
        super().__init__()
        self._buildings = {}
        self._townhall = TownHall()
        self.items = []
        self.item_lookup = {}
        
    def _load_json(self, text_data, th_to_level_map):
        """Load building data from JSON files."""
        try:
            with open(BUILDING_FILE_PATH, "rb") as fp:
                buildings_data = orjson.loads(fp.read())
                
            for building_name, building_data in buildings_data.items():
                # Skip template or placeholder buildings
                if building_name.startswith("Template") or building_name.startswith("Locked"):
                    continue
                    
                # Get user-friendly name from text_data if available
                display_name = building_name
                tid = building_data.get("1", {}).get("TID")
                if tid and tid in text_data:
                    display_name = text_data[tid]
                
                # Create building class
                building_class = type(
                    building_name.replace(" ", ""),
                    (Building,),
                    {'_townhall': self._townhall}
                )
                
                # Load building data
                building_class._load_json_meta(
                    building_data,
                    len(self._buildings) + 1,  # Use incremental ID if not provided
                    display_name or building_name,
                    th_to_level_map
                )
                
                self._buildings[building_name] = building_class
                self.items.append(building_class)
                self.item_lookup[display_name or building_name] = building_class
                
            return self
        except Exception as e:
            logger.error(f"Error loading building data: {e}")
            return self
        
    def get_building_by_name(self, name: str) -> Optional[Type[Building]]:
        """Get a building class by name.
        
        Parameters
        ----------
        name: :class:`str`
            The name of the building to get.
            
        Returns
        -------
        Optional[Type[:class:`Building`]]
            The building class, if found.
        """
        # First try direct lookup
        if name in self.item_lookup:
            return self.item_lookup[name]
            
        # Then try case-insensitive search
        for building_name, building in self._buildings.items():
            if building_name.lower() == name.lower() or building.name.lower() == name.lower():
                return building
                
        return None
    
    def is_valid_townhall(self, th_level: int, buildings: List[Building]) -> bool:
        """Check if a set of buildings meets the requirements for a townhall level.
        
        Parameters
        ----------
        th_level: :class:`int`
            The townhall level to check.
        buildings: List[:class:`Building`]
            The list of buildings to check.
            
        Returns
        -------
        :class:`bool`
            True if the buildings meet the requirements for the given townhall level.
        """
        return self._townhall.validate_buildings(buildings, th_level)
    
    def get_missing_requirements(self, th_level: int, buildings: List[Building]) -> Dict[str, int]:
        """Get the missing or under-leveled buildings for a townhall level.
        
        Parameters
        ----------
        th_level: :class:`int`
            The townhall level to check.
        buildings: List[:class:`Building`]
            The list of buildings to check.
            
        Returns
        -------
        Dict[:class:`str`, :class:`int`]
            A dictionary of building names to required levels that are missing or under-leveled.
        """
        return self._townhall.get_missing_requirements(buildings, th_level)
    
    def get_townhall_building_requirements(self, th_level: int) -> Dict[str, int]:
        """Get all building requirements for a specific townhall level.
        
        Parameters
        ----------
        th_level: :class:`int`
            The townhall level to get requirements for.
            
        Returns
        -------
        Dict[:class:`str`, :class:`int`]
            A dictionary of building names to required levels.
        """
        return self._townhall.get_cumulative_requirements(th_level) 
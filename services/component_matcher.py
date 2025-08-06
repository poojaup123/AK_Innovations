from models import Item, ComponentDetectionTemplate
from app import db
from typing import List, Dict, Optional, Tuple
import difflib
import logging

logger = logging.getLogger(__name__)

class ComponentInventoryMatcher:
    """
    Match detected components with existing inventory items
    Uses fuzzy matching and component templates
    """
    
    def __init__(self):
        self.match_threshold = 0.6  # Minimum similarity score for matches
    
    def match_detections_with_inventory(self, detections: List[Dict]) -> List[Dict]:
        """
        Match detected components with inventory items
        Returns enhanced detection data with inventory matches
        """
        enhanced_detections = []
        
        for detection in detections:
            # Find best inventory match
            match_result = self._find_best_inventory_match(detection)
            
            # Enhance detection with match data
            enhanced_detection = detection.copy()
            enhanced_detection.update({
                'matched_item_id': match_result['item_id'],
                'matched_item_name': match_result['item_name'],
                'matched_item_code': match_result['item_code'],
                'match_confidence': match_result['confidence'],
                'match_method': match_result['method'],
                'suggested_quantity': 1,  # Default to 1, can be adjusted
                'inventory_available': match_result['available_stock'],
                'unit_price': match_result['unit_price']
            })
            
            enhanced_detections.append(enhanced_detection)
        
        return enhanced_detections
    
    def _find_best_inventory_match(self, detection: Dict) -> Dict:
        """Find the best matching inventory item for a detection"""
        component_class = detection['component_class']
        
        # Try different matching strategies
        matches = []
        
        # Strategy 1: Exact class name match
        exact_matches = self._find_exact_matches(component_class)
        matches.extend([(match, 1.0, 'exact') for match in exact_matches])
        
        # Strategy 2: Fuzzy name matching
        fuzzy_matches = self._find_fuzzy_matches(component_class)
        matches.extend(fuzzy_matches)
        
        # Strategy 3: Template matching (if templates exist)
        template_matches = self._find_template_matches(detection)
        matches.extend(template_matches)
        
        # Strategy 4: Category/type matching
        category_matches = self._find_category_matches(component_class)
        matches.extend(category_matches)
        
        # Select best match
        if matches:
            # Sort by confidence score (descending)
            matches.sort(key=lambda x: x[1], reverse=True)
            best_match = matches[0]
            
            item = best_match[0]
            return {
                'item_id': item.id,
                'item_name': item.name,
                'item_code': item.code,
                'confidence': best_match[1],
                'method': best_match[2],
                'available_stock': item.current_stock or 0,
                'unit_price': item.unit_price or 0
            }
        
        # No match found
        return {
            'item_id': None,
            'item_name': None,
            'item_code': None,
            'confidence': 0.0,
            'method': 'no_match',
            'available_stock': 0,
            'unit_price': 0
        }
    
    def _find_exact_matches(self, component_class: str) -> List:
        """Find items with exact name matches"""
        return Item.query.filter(
            Item.name.ilike(f'%{component_class}%')
        ).limit(5).all()
    
    def _find_fuzzy_matches(self, component_class: str) -> List[Tuple]:
        """Find items using fuzzy string matching"""
        matches = []
        
        # Get all items (limit to reasonable number for performance)
        all_items = Item.query.limit(1000).all()
        
        for item in all_items:
            # Compare with item name
            name_similarity = self._calculate_similarity(
                component_class.lower(), 
                item.name.lower()
            )
            
            # Compare with item code if available
            code_similarity = 0
            if item.code:
                code_similarity = self._calculate_similarity(
                    component_class.lower(),
                    item.code.lower()
                )
            
            # Use the higher similarity score
            max_similarity = max(name_similarity, code_similarity)
            
            if max_similarity >= self.match_threshold:
                matches.append((item, max_similarity, 'fuzzy'))
        
        return matches
    
    def _find_template_matches(self, detection: Dict) -> List[Tuple]:
        """Find matches using pre-defined component templates"""
        matches = []
        
        # Get active templates
        templates = ComponentDetectionTemplate.query.filter_by(is_active=True).all()
        
        for template in templates:
            # Basic template matching logic
            # In a full implementation, this would use computer vision
            # to compare the cropped component with template images
            
            # For now, use class name similarity with template name
            if template.template_name:
                similarity = self._calculate_similarity(
                    detection['component_class'].lower(),
                    template.template_name.lower()
                )
                
                if similarity >= template.match_threshold:
                    matches.append((template.item, similarity, 'template'))
        
        return matches
    
    def _find_category_matches(self, component_class: str) -> List[Tuple]:
        """Find matches based on item categories or types"""
        matches = []
        
        # Define category mappings for common component types
        category_mappings = {
            'screw': ['fastener', 'bolt', 'screw'],
            'bolt': ['fastener', 'bolt', 'screw'], 
            'nut': ['fastener', 'nut'],
            'washer': ['fastener', 'washer'],
            'bearing': ['bearing', 'ball bearing'],
            'gear': ['gear', 'cog'],
            'spring': ['spring'],
            'pipe': ['pipe', 'tube'],
            'plate': ['plate', 'sheet'],
            'bracket': ['bracket', 'mount']
        }
        
        # Find relevant categories
        relevant_categories = []
        for category, keywords in category_mappings.items():
            if any(keyword in component_class.lower() for keyword in keywords):
                relevant_categories.extend(keywords)
        
        if relevant_categories:
            # Search for items with these categories in their names or descriptions
            for category in relevant_categories:
                category_items = Item.query.filter(
                    db.or_(
                        Item.name.ilike(f'%{category}%'),
                        Item.description.ilike(f'%{category}%') if Item.description else False
                    )
                ).limit(10).all()
                
                for item in category_items:
                    similarity = 0.7  # Medium confidence for category matches
                    matches.append((item, similarity, 'category'))
        
        return matches
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using difflib"""
        return difflib.SequenceMatcher(None, str1, str2).ratio()
    
    def suggest_inventory_actions(self, enhanced_detections: List[Dict]) -> Dict:
        """Suggest inventory-related actions based on detections"""
        suggestions = {
            'matched_components': 0,
            'unmatched_components': 0,
            'low_stock_warnings': [],
            'new_item_suggestions': [],
            'total_estimated_value': 0
        }
        
        for detection in enhanced_detections:
            if detection['matched_item_id']:
                suggestions['matched_components'] += 1
                
                # Check stock levels
                if detection['inventory_available'] < 10:  # Low stock threshold
                    suggestions['low_stock_warnings'].append({
                        'item_name': detection['matched_item_name'],
                        'current_stock': detection['inventory_available'],
                        'detected_component': detection['component_class']
                    })
                
                # Add to estimated value
                suggestions['total_estimated_value'] += detection['unit_price']
                
            else:
                suggestions['unmatched_components'] += 1
                suggestions['new_item_suggestions'].append({
                    'detected_class': detection['component_class'],
                    'confidence': detection['confidence'],
                    'estimated_dimensions': {
                        'width_mm': detection['estimated_width_mm'],
                        'height_mm': detection['estimated_height_mm'],
                        'area_mm2': detection['estimated_area_mm2']
                    }
                })
        
        return suggestions
    
    def create_bom_from_detections(self, enhanced_detections: List[Dict], 
                                 product_name: str) -> Dict:
        """Create a Bill of Materials from detected components"""
        bom_items = []
        
        # Group detections by matched item
        item_groups = {}
        for detection in enhanced_detections:
            if detection['matched_item_id']:
                item_id = detection['matched_item_id']
                if item_id not in item_groups:
                    item_groups[item_id] = {
                        'item_name': detection['matched_item_name'],
                        'item_code': detection['matched_item_code'],
                        'unit_price': detection['unit_price'],
                        'quantity': 0
                    }
                item_groups[item_id]['quantity'] += detection['suggested_quantity']
        
        # Convert to BOM format
        for item_id, item_data in item_groups.items():
            bom_items.append({
                'item_id': item_id,
                'item_name': item_data['item_name'],
                'item_code': item_data['item_code'],
                'quantity_required': item_data['quantity'],
                'unit_price': item_data['unit_price'],
                'total_cost': item_data['quantity'] * item_data['unit_price']
            })
        
        return {
            'product_name': product_name,
            'total_items': len(bom_items),
            'total_cost': sum(item['total_cost'] for item in bom_items),
            'items': bom_items,
            'unmatched_components': [
                d for d in enhanced_detections if not d['matched_item_id']
            ]
        }
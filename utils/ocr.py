"""
OCR Utility Functions for Receipt/Invoice Processing
Extracts structured data from uploaded receipt/invoice images
"""

import os
import re
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from datetime import datetime
from dateutil import parser
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReceiptOCR:
    def __init__(self):
        """Initialize OCR processor with configuration"""
        # Common patterns for different fields
        self.patterns = {
            'amount': [
                r'(?:total|amount|₹|rs\.?|inr)\s*:?\s*(\d+(?:\.\d{2})?)',
                r'(\d+\.\d{2})\s*(?:total|amount)',
                r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
                r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*₹'
            ],
            'gst': [
                r'gst\s*:?\s*(\d+(?:\.\d{2})?%?)',
                r'tax\s*:?\s*(\d+(?:\.\d{2})?)',
                r'cgst\s*:?\s*(\d+(?:\.\d{2})?)',
                r'sgst\s*:?\s*(\d+(?:\.\d{2})?)',
                r'igst\s*:?\s*(\d+(?:\.\d{2})?)'
            ],
            'date': [
                r'date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})'
            ],
            'vendor': [
                r'(?:vendor|seller|from|company)\s*:?\s*([a-zA-Z\s&\.]+)',
                r'^([A-Z][a-zA-Z\s&\.]{5,30})',  # Company name patterns
                r'([A-Z]{2,}\s+[A-Z]{2,})',  # All caps company names
            ],
            'gstin': [
                r'(?:gstin|gst\s*no|tax\s*id)\s*:?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})',
                r'([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})'
            ],
            'invoice_number': [
                r'(?:invoice|bill|receipt)\s*(?:no|number|#)\s*:?\s*([A-Z0-9\-/]+)',
                r'(?:inv|bill)[\s#]*([A-Z0-9\-/]+)'
            ]
        }
    
    def preprocess_image(self, image_path):
        """Preprocess image for better OCR accuracy using PIL"""
        try:
            # Open image with PIL
            img = Image.open(image_path)
            
            # Convert to grayscale
            gray = img.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(2.0)
            
            # Apply sharpening filter
            sharpened = enhanced.filter(ImageFilter.SHARPEN)
            
            # Save preprocessed image temporarily
            temp_path = image_path.replace('.', '_processed.')
            sharpened.save(temp_path)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error preprocessing image: {str(e)}")
            return image_path  # Return original if preprocessing fails
    
    def extract_text(self, image_path):
        """Extract text from image using Tesseract OCR"""
        try:
            # Preprocess image
            processed_path = self.preprocess_image(image_path)
            
            # Configure Tesseract for better accuracy
            custom_config = r'--oem 3 --psm 6 -l eng'
            
            # Extract text
            text = pytesseract.image_to_string(Image.open(processed_path), config=custom_config)
            
            # Clean up temporary file if created
            if processed_path != image_path and os.path.exists(processed_path):
                os.remove(processed_path)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            return ""
    
    def parse_field(self, text, field_type):
        """Parse specific field from extracted text"""
        if field_type not in self.patterns:
            return None
        
        # Convert to lowercase for pattern matching
        text_lower = text.lower()
        
        for pattern in self.patterns[field_type]:
            matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if matches:
                return self.clean_field_value(matches[0], field_type)
        
        return None
    
    def clean_field_value(self, value, field_type):
        """Clean and format extracted field values"""
        if not value:
            return None
        
        try:
            if field_type == 'amount':
                # Remove commas and convert to float
                amount_str = str(value).replace(',', '').replace('₹', '').strip()
                return float(amount_str)
            
            elif field_type == 'gst':
                # Extract numeric value from GST
                gst_str = str(value).replace('%', '').strip()
                return float(gst_str)
            
            elif field_type == 'date':
                # Parse date string
                try:
                    parsed_date = parser.parse(str(value), fuzzy=True)
                    return parsed_date.strftime('%Y-%m-%d')
                except:
                    return None
            
            elif field_type in ['vendor', 'invoice_number']:
                # Clean string fields
                return str(value).strip().title()
            
            elif field_type == 'gstin':
                # Clean GSTIN
                return str(value).upper().strip()
            
            else:
                return str(value).strip()
                
        except Exception as e:
            logger.error(f"Error cleaning field {field_type}: {str(e)}")
            return None
    
    def categorize_expense(self, text, vendor=None):
        """Automatically categorize expense based on text content"""
        text_lower = text.lower()
        
        # Define category keywords
        categories = {
            'utilities': ['electricity', 'water', 'gas', 'internet', 'phone', 'utility', 'power', 'electric'],
            'maintenance': ['repair', 'maintenance', 'service', 'fix', 'cleaning', 'painting'],
            'materials': ['steel', 'iron', 'raw material', 'component', 'parts', 'supplies'],
            'transport': ['fuel', 'diesel', 'petrol', 'transport', 'delivery', 'shipping', 'freight'],
            'overhead': ['rent', 'office', 'insurance', 'license', 'registration'],
            'salaries': ['salary', 'wages', 'bonus', 'allowance', 'employee']
        }
        
        # Check text for category keywords
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower or (vendor and keyword in vendor.lower()):
                    return category.title()
        
        return 'Others'  # Default category
    
    def extract_structured_data(self, image_path):
        """Extract all structured data from receipt/invoice image"""
        try:
            # Extract raw text
            raw_text = self.extract_text(image_path)
            if not raw_text:
                return {'error': 'Could not extract text from image'}
            
            # Parse individual fields
            extracted_data = {
                'raw_text': raw_text,
                'amount': self.parse_field(raw_text, 'amount'),
                'gst_amount': self.parse_field(raw_text, 'gst'),
                'date': self.parse_field(raw_text, 'date'),
                'vendor': self.parse_field(raw_text, 'vendor'),
                'gstin': self.parse_field(raw_text, 'gstin'),
                'invoice_number': self.parse_field(raw_text, 'invoice_number')
            }
            
            # Auto-categorize expense
            extracted_data['category'] = self.categorize_expense(raw_text, extracted_data['vendor'])
            
            # Calculate base amount if GST is found
            if extracted_data['amount'] and extracted_data['gst_amount']:
                try:
                    total_amount = extracted_data['amount']
                    gst_rate = extracted_data['gst_amount']
                    if gst_rate > 1:  # If GST is given as percentage
                        gst_rate = gst_rate / 100
                    
                    # Calculate base amount (total / (1 + gst_rate))
                    base_amount = total_amount / (1 + gst_rate)
                    tax_amount = total_amount - base_amount
                    
                    extracted_data['base_amount'] = round(base_amount, 2)
                    extracted_data['tax_amount'] = round(tax_amount, 2)
                    extracted_data['gst_rate'] = gst_rate * 100  # Convert back to percentage
                except:
                    pass
            
            # Add confidence indicators
            extracted_data['confidence'] = self.calculate_confidence(extracted_data)
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error extracting structured data: {str(e)}")
            return {'error': f'OCR processing failed: {str(e)}'}
    
    def calculate_confidence(self, data):
        """Calculate confidence score based on extracted fields"""
        score = 0
        total_fields = 6  # Total important fields
        
        if data.get('amount'):
            score += 2  # Amount is most important
        if data.get('date'):
            score += 1
        if data.get('vendor'):
            score += 1
        if data.get('gst_amount'):
            score += 1
        if data.get('invoice_number'):
            score += 0.5
        if data.get('gstin'):
            score += 0.5
        
        return min(round((score / total_fields) * 100), 100)

# Convenience function for easy import
def process_receipt_image(image_path):
    """Process receipt image and return structured data"""
    ocr = ReceiptOCR()
    return ocr.extract_structured_data(image_path)
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
import email
from email.mime.text import MIMEText


class ReceiptParser:
    def __init__(self):
        # Common patterns for extracting merchant, amount, and date
        self.merchant_patterns = [
            r'(?:from|merchant|vendor|store):\s*([^\n\r]+)',
            r'^([A-Z][A-Z\s&]+)\s*$',  # All caps merchant names
            r'([A-Za-z\s&]+)\s*receipt',
            r'([A-Za-z\s&]+)\s*invoice',
        ]
        
        self.amount_patterns = [
            r'(?:total|amount|price|cost):\s*[₹$]?(\d+(?:\.\d{2})?)',
            r'[₹$](\d+(?:\.\d{2})?)',
            r'(\d+(?:\.\d{2})?)\s*(?:rupees|rs|dollars|usd)',
        ]
        
        self.date_patterns = [
            r'(?:date|on):\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'(\d{4}-\d{2}-\d{2})',  # ISO format
        ]

    def parse_text_receipt(self, content: str) -> Dict[str, any]:
        """Parse a text receipt and extract merchant, amount, and date"""
        content = content.strip()
        
        merchant = self._extract_merchant(content)
        amount = self._extract_amount(content)
        date = self._extract_date(content)
        
        return {
            "merchant": merchant,
            "amount": amount,
            "date": date,
            "raw_content": content[:500]  # Store first 500 chars for reference
        }

    def parse_eml_file(self, content: bytes) -> Dict[str, any]:
        """Parse an .eml file and extract receipt information"""
        try:
            msg = email.message_from_bytes(content)
            
            # Extract text content
            text_content = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        text_content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                text_content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Parse the extracted text
            result = self.parse_text_receipt(text_content)
            
            # Add email-specific information
            result["source"] = "email"
            result["email_subject"] = msg.get("Subject", "")
            result["email_from"] = msg.get("From", "")
            
            return result
            
        except Exception as e:
            # Fallback to text parsing
            text_content = content.decode('utf-8', errors='ignore')
            result = self.parse_text_receipt(text_content)
            result["source"] = "email"
            result["parse_error"] = str(e)
            return result

    def _extract_merchant(self, content: str) -> Optional[str]:
        """Extract merchant name from content"""
        for pattern in self.merchant_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                merchant = match.group(1).strip()
                if len(merchant) > 2 and len(merchant) < 100:  # Reasonable length
                    return merchant
        
        # Fallback: look for common merchant patterns
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if len(line) > 3 and len(line) < 50 and not re.search(r'\d', line):
                # Line without numbers, might be merchant name
                return line
        
        return "Unknown Merchant"

    def _extract_amount(self, content: str) -> Optional[float]:
        """Extract amount from content"""
        for pattern in self.amount_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1))
                    if 0 < amount < 100000:  # Reasonable amount range
                        return amount
                except ValueError:
                    continue
        
        return None

    def _extract_date(self, content: str) -> Optional[datetime]:
        """Extract date from content"""
        for pattern in self.date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    # Try different date formats
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%y', '%d-%m-%y']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except:
                    continue
        
        # Fallback to current date
        return datetime.now()


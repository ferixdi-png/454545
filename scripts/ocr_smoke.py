"""
OCR smoke test - verify Tesseract availability.

Diagnostic tool for OCR subsystem.
"""
import sys
import os

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def check_tesseract():
    """Check Tesseract availability."""
    print("=" * 60)
    print("OCR SMOKE TEST - TESSERACT")
    print("=" * 60)
    
    try:
        import pytesseract
        
        # Get version
        version = pytesseract.get_tesseract_version()
        print(f"\n✅ Tesseract found")
        print(f"   Version: {version}")
        
        # Get path
        try:
            cmd = pytesseract.pytesseract.tesseract_cmd
            print(f"   Path: {cmd}")
        except:
            print(f"   Path: (default)")
        
        # Test recognition only if PIL available
        if HAS_PIL:
            print(f"\n🧪 Testing recognition...")
            
            # Create test image
            img = Image.new('RGB', (200, 50), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "PAY 1234", fill='black')
            
            # Recognize
            text = pytesseract.image_to_string(img).strip()
            print(f"   Input: 'PAY 1234'")
            print(f"   Output: '{text}'")
            
            if "PAY" in text or "1234" in text:
                print(f"   ✅ Recognition OK")
            else:
                print(f"   ⚠️  Recognition quality low")
        else:
            print(f"\n⚠️  PIL not available - skipping recognition test")
        
        print("\n" + "=" * 60)
        print("✅ OCR SMOKE TEST PASSED")
        print("=" * 60)
        return True
        
    except ImportError:
        print(f"\n❌ pytesseract not installed")
        print(f"   Install: pip install pytesseract")
        return False
        
    except Exception as e:
        print(f"\n⚠️  Tesseract unavailable: {e}")
        print(f"   Fallback: OCR will use stub mode")
        return False


if __name__ == "__main__":
    success = check_tesseract()
    sys.exit(0 if success else 1)

import base64
import logging
import cv2
import numpy as np
import onnxruntime as ort
import insightface
from insightface.app import FaceAnalysis

logger = logging.getLogger(__name__)

class FaceService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FaceService, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        available_providers = ort.get_available_providers()
        logger.info(f"Available ONNX Runtime providers: {available_providers}")
        
        # Use CUDA if available, else CPU
        provider = 'CUDAExecutionProvider' if 'CUDAExecutionProvider' in available_providers else 'CPUExecutionProvider'
        logger.info(f"Initializing InsightFace with provider: {provider}")
        
        try:
            # Load buffalo_l SCRFD detector and ArcFace model
            self.app = FaceAnalysis(name='buffalo_l', providers=[provider])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            self._initialized = True
            logger.info("InsightFace FaceAnalysis initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize InsightFace: {e}", exc_info=True)
            raise e

    def decode_base64_image(self, base64_str: str) -> np.ndarray:
        """
        Decodes a base64 encoded image string into an OpenCV BGR image array.
        """
        try:
            if ',' in base64_str:
                # Strip data URI header
                base64_str = base64_str.split(',', 1)[1]
            image_bytes = base64_str.encode('utf-8')
            decoded_bytes = base64.b64decode(image_bytes)
            nparr = np.frombuffer(decoded_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("cv2.imdecode returned None. Invalid image content.")
            return img
        except Exception as e:
            logger.error(f"Error decoding base64 image: {e}")
            raise ValueError(f"Failed to decode image data: {str(e)}")

    def detect_and_extract_face_embedding(self, img: np.ndarray) -> np.ndarray:
        """
        Detects faces in the image, validates size/count/confidence, 
        and extracts the 512-dimensional L2-normalized embedding.
        """
        if img is None:
            raise ValueError("Invalid image array.")

        try:
            faces = self.app.get(img)
        except Exception as e:
            logger.error(f"Error executing face detection: {e}", exc_info=True)
            raise ValueError(f"Face model analysis error: {str(e)}")

        # Reject if no face
        if len(faces) == 0:
            raise ValueError("No face detected in the image.")

        # Reject if multiple faces
        if len(faces) > 1:
            raise ValueError("Multiple faces detected. Please ensure only one face is visible in the frame.")

        face = faces[0]

        # Reject if low detection confidence (<0.65)
        if getattr(face, 'det_score', 0.0) < 0.65:
            raise ValueError(f"Face detection confidence too low ({face.det_score:.2f}). Please ensure good lighting.")

        # Reject if face too small (<100px)
        bbox = face.bbox.astype(int)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width < 100 or height < 100:
            raise ValueError(f"Face is too small in the frame ({width}x{height}px). Please move closer to the camera (minimum size 100x100px).")

        # Extract and normalize embedding
        embedding = face.embedding
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return embedding

    def calculate_cosine_similarity(self, embedding_a: np.ndarray, embedding_b: np.ndarray) -> float:
        """
        Computes the cosine similarity between two L2-normalized embedding vectors.
        Because they are already L2-normalized, this is equivalent to the dot product.
        """
        # Ensure L2-normalized numpy arrays
        a = np.array(embedding_a)
        b = np.array(embedding_b)
        
        # Cosine similarity (dot product)
        similarity = float(np.dot(a, b))
        return similarity

_face_service_instance = None

def get_face_service() -> FaceService:
    global _face_service_instance
    if _face_service_instance is None:
        _face_service_instance = FaceService()
    return _face_service_instance

import { Component, inject, signal, ElementRef, ViewChild, ChangeDetectorRef, OnDestroy, AfterViewInit } from '@angular/core';
import { Router } from '@angular/router';
import { Auth } from '../../services/auth';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import lottie, { AnimationItem } from 'lottie-web';

@Component({
  selector: 'app-login',
  imports: [FormsModule, CommonModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
  standalone: true
})
export class Login implements OnDestroy, AfterViewInit {
  private auth = inject(Auth);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  @ViewChild('lottieContainer', { static: false }) lottieContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('webcamVideo') webcamVideo!: ElementRef<HTMLVideoElement>;

  email = '';
  password = '';
  errorMessage = signal<string | null>(null);
  isLoading = signal<boolean>(false);

  isFaceLoginActive = signal<boolean>(false);
  isCameraActive = signal<boolean>(false);
  isProcessingFace = signal<boolean>(false);
  faceScanError = signal<string | null>(null);
  faceScanSuccess = signal<string | null>(null);
  cameraStream: MediaStream | null = null;
  lottieAnimation: AnimationItem | null = null;

  ngAfterViewInit(): void {
    if (this.lottieContainer?.nativeElement) {
      this.lottieAnimation = lottie.loadAnimation({
        container: this.lottieContainer.nativeElement,
        renderer: 'canvas',
        loop: true,
        autoplay: true,
        path: '/Supply%20Chain%20and%20Shipping.json',
        rendererSettings: {
          preserveAspectRatio: 'xMidYMid slice',
          progressiveLoad: true,
          clearCanvas: true
        }
      });
    }
  }

  ngOnDestroy(): void {
    this.destroyLottie();
    this.stopCamera();
  }

  onSubmit(): void {
    if (!this.email || !this.password) {
      this.errorMessage.set('Please fill out all fields.');
      return;
    }

    this.isLoading.set(true);
    this.errorMessage.set(null);

    this.auth.login(this.email, this.password).subscribe({
      next: (res) => {
        this.isLoading.set(false);
        if (res && res.status === 'face_verification_required') {
          this.isFaceLoginActive.set(true);
          this.startCamera();
          this.faceScanSuccess.set('Password verified! Center face in camera feed to complete supplier login.');
          return;
        }

        if (res && res.role === 'supplier') {
          this.router.navigate(['/supplier']);
        } else {
          this.router.navigate(['/']);
        }
      },
      error: (err) => {
        this.isLoading.set(false);
        if (err.status === 0) {
          this.errorMessage.set('Cannot connect to backend server. Make sure FastAPI is running.');
        } else {
          this.errorMessage.set(err.error?.detail || 'Invalid email or password.');
        }
      }
    });
  }

  cancelFaceLogin(): void {
    this.stopCamera();
    this.isFaceLoginActive.set(false);
    this.errorMessage.set(null);
    this.faceScanError.set(null);
    this.faceScanSuccess.set(null);
  }

  startCamera(): void {
    this.isCameraActive.set(false);
    this.faceScanError.set(null);
    this.faceScanSuccess.set(null);

    navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    }).then(stream => {
      this.cameraStream = stream;
      this.isCameraActive.set(true);
      this.cdr.detectChanges();
// hook up camera feed to the video player after a brief delay so Angular can mount the DOM elements first
      setTimeout(() => {
        if (this.webcamVideo && this.webcamVideo.nativeElement) {
          this.webcamVideo.nativeElement.srcObject = stream;
          this.webcamVideo.nativeElement.play().catch(err => {
            console.error('Error starting video stream playback:', err);
          });
        }
      }, 100);
    }).catch(err => {
      console.error('Webcam access error during login:', err);
      this.faceScanError.set('Could not access webcam. Please verify browser permissions.');
      this.isCameraActive.set(false);
      this.cdr.detectChanges();
    });
  }

  stopCamera(): void {
    if (this.cameraStream) {
      this.cameraStream.getTracks().forEach(track => track.stop());
      this.cameraStream = null;
    }
    this.isCameraActive.set(false);
    this.isProcessingFace.set(false);
  }

  destroyLottie(): void {
    if (this.lottieAnimation) {
      this.lottieAnimation.destroy();
      this.lottieAnimation = null;
    }
  }

  loginWithFace(): void {
    if (!this.webcamVideo || !this.isCameraActive()) return;

    this.isProcessingFace.set(true);
    this.faceScanError.set(null);
    this.faceScanSuccess.set(null);
    this.cdr.detectChanges();

    const videoEl = this.webcamVideo.nativeElement;
    const canvas = document.createElement('canvas');
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      this.faceScanError.set('Failed to initialize capture canvas.');
      this.isProcessingFace.set(false);
      return;
    }
    // project the current video frame onto a canvas to capture the image
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    const base64Data = canvas.toDataURL('image/jpeg', 0.9);// serialize to base64 JPEG at 90% quality to avoid sending massive payloads over HTTP

    // authenticate via biometric matching (1-to-1 matching if email is provided, else fallback to 1-to-many lookup)
    const emailFilter = this.email.trim() || undefined;

    this.auth.loginFace(base64Data, emailFilter).subscribe({
      next: (user) => {
        this.faceScanSuccess.set('Face ID Verified! Logging in...');
        this.isProcessingFace.set(false);
        this.cdr.detectChanges();

        setTimeout(() => {
          this.stopCamera();
          if (user && user.role === 'supplier') {
            this.router.navigate(['/supplier']);
          } else {
            this.router.navigate(['/']);
          }
        }, 1000);
      },
      error: (err) => {
        console.error('Face ID Login failed:', err);
        const errMsg = err.error?.detail || 'Face recognition matching failed. Please align your face and try again.';
        this.faceScanError.set(errMsg);
        this.isProcessingFace.set(false);
        this.cdr.detectChanges();
      }
    });
  }
}

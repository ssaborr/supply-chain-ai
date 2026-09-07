import { Component, OnInit, inject, ViewChild, ElementRef, AfterViewChecked, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '../../services/auth';
import { Router } from '@angular/router';
import { I18nService } from '../../services/i18n';
import { TranslatePipe } from '../../pipes/translate.pipe';

interface Message {
  sender: 'user' | 'bot';
  text: string;
  time: string;
}

@Component({
  selector: 'app-chatbot-widget',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './chatbot-widget.html',
  styleUrl: './chatbot-widget.css'
})
export class ChatbotWidget implements OnInit, AfterViewChecked {
  private http = inject(HttpClient);
  public auth = inject(Auth);
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  private i18n = inject(I18nService);

  @ViewChild('messageContainer') private messageContainer!: ElementRef;

  public isOpen: boolean = false;
  public userMessage: string = '';
  public isTyping: boolean = false;
  public messages: Message[] = [];

  ngOnInit(): void {
    this.messages.push({
      sender: 'bot',
      text: this.parseMarkdown(this.i18n.t('chatbot.welcome')),
      time: this.getCurrentTime()
    });
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  public toggleChat(): void {
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.cdr.detectChanges();
      this.scrollToBottom();
    }
  }

  public sendMessage(): void {
    const text = this.userMessage.trim();
    if (!text) return;

    this.messages.push({
      sender: 'user',
      text: this.parseMarkdown(text),
      time: this.getCurrentTime()
    });

    this.userMessage = '';
    this.isTyping = true;
    this.scrollToBottom();

    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    const url = `/api/chatbot/query${this.i18n.apiLanguageQuery()}`;
    this.http.post<any>(url, { message: text }, { headers }).subscribe({
      next: (res) => {
        this.isTyping = false;
        this.messages.push({
          sender: 'bot',
          text: this.parseMarkdown(res.response),
          time: this.getCurrentTime()
        });
        this.cdr.detectChanges();
        this.scrollToBottom();
      },
      error: (err) => {
        console.error('Chatbot error:', err);
        this.isTyping = false;
        this.messages.push({
          sender: 'bot',
          text: this.parseMarkdown(this.i18n.t('chatbot.error')),
          time: this.getCurrentTime()
        });
        this.cdr.detectChanges();
        this.scrollToBottom();
      }
    });
  }

  public onKeyPress(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      this.sendMessage();
    }
  }

  public parseMarkdown(text: string): string {
    if (!text) return '';
    let escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');

    escaped = escaped.replace(/\n/g, '<br>');

    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    escaped = escaped.replace(/•\s*(.*?)(?:<br>|$)/g, '• $1<br>');
    escaped = escaped.replace(/\*\s*(.*?)(?:<br>|$)/g, '• $1<br>');

    escaped = escaped.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">$1</a>');

    return escaped;
  }

  private getCurrentTime(): string {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
  }

  private scrollToBottom(): void {
    if (this.messageContainer) {
      try {
        this.messageContainer.nativeElement.scrollTop = this.messageContainer.nativeElement.scrollHeight;
      } catch (err) {
      }
    }
  }

  public triggerAttachment(): void {
    alert('Attachment functionality is under development.');
  }

  public triggerOptions(): void {
    alert('Options menu opened.');
  }

  public handleMessageClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (target && target.tagName === 'A') {
      const href = target.getAttribute('href');
      if (href) {
        if (href.includes('/sales-order')) {
          event.preventDefault();
          try {
            const urlObj = new URL(href, window.location.origin);
            const orderId = urlObj.searchParams.get('orderId');
            this.router.navigate(['/sales-order'], {
              queryParams: { orderId: orderId }
            });
          } catch (e) {
            const match = href.match(/orderId=(\d+)/);
            if (match) {
              this.router.navigate(['/sales-order'], {
                queryParams: { orderId: match[1] }
              });
            }
          }
        }
      }
    }
  }
}

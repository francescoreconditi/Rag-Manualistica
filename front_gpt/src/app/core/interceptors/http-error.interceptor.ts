import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { NotificationService } from '../services/notification.service';

export const httpErrorInterceptor: HttpInterceptorFn = (req, next) => {
  const notifier = inject(NotificationService);

  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        const status = error.status;
        const serverMessage =
          typeof error.error === 'string'
            ? error.error
            : error.error?.detail ?? error.message;

        const readable = buildReadableMessage(status, serverMessage);
        notifier.error(readable);
      } else {
        notifier.error('Errore imprevisto durante la chiamata API.');
      }

      return throwError(() => error);
    })
  );
};

function buildReadableMessage(status: number, message: string): string {
  switch (status) {
    case 0:
      return 'Impossibile contattare il server. Verifica la connessione o l\'URL delle API.';
    case 400:
      return `Richiesta non valida: ${message}`;
    case 401:
      return 'Non autorizzato. Controlla le credenziali o la configurazione della chiave API.';
    case 404:
      return 'Risorsa non trovata. Assicurati che il servizio RAG sia in esecuzione.';
    case 500:
      return `Errore interno del server: ${message}`;
    default:
      return `Errore (${status}): ${message}`;
  }
}

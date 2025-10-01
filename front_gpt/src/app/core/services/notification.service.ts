import { Injectable } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable({ providedIn: 'root' })
export class NotificationService {
  constructor(private readonly snackBar: MatSnackBar) {}

  success(message: string, action = 'OK', duration = 3500): void {
    this.snackBar.open(message, action, {
      duration,
      panelClass: ['snackbar-success']
    });
  }

  error(message: string, action = 'Chiudi', duration = 5000): void {
    this.snackBar.open(message, action, {
      duration,
      panelClass: ['snackbar-error']
    });
  }

  info(message: string, action = 'OK', duration = 4000): void {
    this.snackBar.open(message, action, {
      duration,
      panelClass: ['snackbar-info']
    });
  }
}

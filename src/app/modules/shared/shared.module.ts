import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TimeAgoPipe } from './pipes/time-ago.pipe';
import { ImgComponent } from './components/img/img.component';
import { RouterModule } from '@angular/router';
import { ShortDescriptionPipe } from './pipes/short-description.pipe';
import { ShortNamePipe } from './pipes/short-author.pipe';
import { KeysPipe } from './pipes/keys.pipe';



@NgModule({
  declarations: [
    ImgComponent,
    TimeAgoPipe,
    ShortDescriptionPipe,
    ShortNamePipe,
    KeysPipe
  ],
  imports: [
    CommonModule,
    RouterModule
  ],
  exports: [
    ImgComponent,
    TimeAgoPipe,
    ShortDescriptionPipe,
    ShortNamePipe,
    KeysPipe
  ]
})
export class SharedModule { }
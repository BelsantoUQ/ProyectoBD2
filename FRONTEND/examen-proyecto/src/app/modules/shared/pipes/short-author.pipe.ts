import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'shortName'
})
export class ShortNamePipe implements PipeTransform {

  private shortSummary:string='';
  transform(summary: string): string {
    this.shortSummary='';
    if(summary.length>12){
      for (let i = 0; i < 12; i++) {
        this.shortSummary=this.shortSummary+summary.charAt(i);
      }
      this.shortSummary = `${this.shortSummary}...`
      return this.shortSummary;
    }
    return summary;

  }

}

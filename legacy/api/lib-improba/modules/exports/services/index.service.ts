import { Injectable, Inject, NotFoundException, forwardRef } from "@nestjs/common";
import { BaseService } from '@lib-improba/base/base.service';
import axios from 'axios';
import * as fs from 'fs';
import * as Handlebars from 'handlebars';

// These are the URLs of the services that we use to convert HTML to Docx
const URL_HTML2PDF_API = process.env.URL_HTML2PDF_API || 'http://html2pdf:3000';
const URL_PANDOC_API = process.env.URL_PANDOC_API || 'http://pandoc:80';

/**
 * ExportService is a service that converts HTML to Docx and PDF
 * It uses the HTML2PDF and Pandoc services to convert HTML to Docx and PDF
 * It also writes the files to the outputPath if provided
 * If the outputPath is not provided, it returns the file as raw data
 */
@Injectable()
export class ExportService  {
  constructor() {}

  private async replaceVariables(html: string, variables: Record<string, string>) {
    const str = Handlebars.compile(html)(variables);
    return str;
  }

  /**
   * Convert HTML to Docx
   * @param options - The options for the conversion
   * @param options.html - The HTML to convert
   * @param options.outputPath - The path to save the Docx file
   * @returns The path to the Docx file if outputPath is provided, otherwise the Docx file as raw data
   */
  async toDocx(options: {
    html: string;
    outputPath?: string;
    variables?: Record<string, string>;
  }) {
    const pandocApiUrl = URL_PANDOC_API;

    const variables = options.variables || {};

    const html = await this.replaceVariables(options.html, variables);

    const response = await axios.post(pandocApiUrl, html, {
      responseType: 'stream',
      timeout: 120000,
      headers: {
        'Content-Type': 'text/html',
        'Accept': 'docx',
      },
    });

    // response.data is the docx file

    // If outputPath is provided, write the file to the outputPath
    // And return the outputPath
    if (options.outputPath) {
      await fs.promises.writeFile(options.outputPath, response.data);
      return options.outputPath;
    }

    // If outputPath is not provided, return the docx file as raw data
    return response.data;
  }

  /**
   * Convert HTML to PDF
   * @param options - The options for the conversion
   * @param options.html - The HTML to convert
   * @param options.outputPath - The path to save the PDF file
   * @returns The path to the PDF file if outputPath is provided, otherwise the PDF file as raw data
   */
  async toPdf(options: {
    html: string;
    outputPath?: string;
    variables?: Record<string, string>;
  }) {
    const html2pdfApiUrl = URL_HTML2PDF_API;

    const variables = options.variables || {};

    const html = await this.replaceVariables(options.html, variables);

    const response = await axios.post(html2pdfApiUrl, html, {
      responseType: 'stream',
      timeout: 120000,
      headers: {
        'Content-Type': 'text/html',
      },
    });

    // response.data is the PDF file

    if (options.outputPath) {
      await fs.promises.writeFile(options.outputPath, response.data);
      return options.outputPath;
    }

    return response.data;
  }
}